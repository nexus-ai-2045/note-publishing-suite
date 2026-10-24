#!/usr/bin/env python3
"""記事別の採用履歴を外部SSOTに保存し、次の入口で現稿との一致を検査する。"""
from __future__ import annotations

import importlib.util

import argparse
import difflib
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

_LOADER_SPEC = importlib.util.spec_from_file_location(
    "_nps_loader_bootstrap", Path(__file__).with_name("nps_script_loader.py"))
if _LOADER_SPEC is None or _LOADER_SPEC.loader is None:
    raise ImportError("cannot load NPS script loader")
_LOADER_MODULE = importlib.util.module_from_spec(_LOADER_SPEC)
_LOADER_SPEC.loader.exec_module(_LOADER_MODULE)
_load_sibling_module = _LOADER_MODULE.load_script


SCHEMA = "nps-article-feedback/v1"
InputCapture = tuple[dict[str, str], dict[str, bytes]]


def remember_input_path(capture: InputCapture, selected: Path, resolved: Path) -> None:
    """Retain the first binding established by the existing path resolver."""
    if capture[0].setdefault(str(selected.absolute()), str(resolved)) != str(resolved):
        raise ValueError("入力pathの初回解決先が変更されています")


def remember_input_bytes(capture: InputCapture, resolved: Path, raw: bytes) -> None:
    if capture[1].setdefault(str(resolved), raw) != raw:
        raise ValueError("入力の初回bytesが変更されています")


def check_input_capture(capture: InputCapture) -> None:
    if (any(str(Path(selected).resolve()) != resolved for selected, resolved in capture[0].items())
            or any(Path(resolved).read_bytes() != raw for resolved, raw in capture[1].items())):
        raise ValueError("入力の初回snapshotが読取り中に変更されています")


def validate_history_policy(value: Any) -> dict:
    if (not isinstance(value, dict) or value.get("schema") != "nps-history-learning-policy/v1"
            or type(value.get("required")) is not bool):
        raise ValueError("history_learning_policyが不正です")
    result = {"schema": value["schema"], "required": value["required"]}
    if "required_sources" in value:
        rows = value["required_sources"]
        if not isinstance(rows, list) or not rows:
            raise ValueError("required_sourcesは空でない配列が必要です")
        ids = set()
        for row in rows:
            if (not isinstance(row, dict)
                    or any(not isinstance(row.get(key), str) or not row[key].strip()
                           for key in ("id", "path", "quote", "evidence_ref"))
                    or row["id"] in ids):
                raise ValueError("required_sourcesの根拠が不足または重複しています")
            if "json_pointer" in row and (not isinstance(row["json_pointer"], str)
                                           or not row["json_pointer"].startswith("/")):
                raise ValueError("required_sourcesのJSON pointerが不正です")
            ids.add(row["id"])
        result["required_sources"] = [dict(row) for row in rows]
    if "vocabulary_rules" in value:
        rules = value["vocabulary_rules"]
        if not isinstance(rules, list) or not rules:
            raise ValueError("vocabulary_rulesは空でない配列が必要です")
        ids = set()
        for rule in rules:
            if (not isinstance(rule, dict)
                    or any(not isinstance(rule.get(key), str) or not rule[key].strip()
                           for key in ("id", "avoid", "preferred"))
                    or any('\n' in rule[key] or '\r' in rule[key] for key in ("avoid", "preferred"))
                    or rule["id"] in ids or rule["avoid"] == rule["preferred"]):
                raise ValueError("vocabulary ruleの宣言が不正です")
            compounds = rule.get("excluded_compounds")
            if (not isinstance(compounds, list)
                    or any(not isinstance(term, str) or rule["avoid"] not in term
                           or term == rule["avoid"] for term in compounds)
                    or len(set(compounds)) != len(compounds)):
                raise ValueError("vocabulary ruleの複合語が不正です")
            ids.add(rule["id"])
        result["vocabulary_rules"] = [dict(rule, excluded_compounds=list(rule["excluded_compounds"]))
                                      for rule in rules]
    return result


def article_history_policy(style: dict, article_id: str | None) -> dict | None:
    """全体の必須条件へ選択記事の条件を加える。別記事へは伝播しない。"""
    policies = []
    if "history_learning_policy" in style:
        policies.append(validate_history_policy(style["history_learning_policy"]))
    profiles = style.get("article_profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("article_profilesが不正です")
    for key, profile in profiles.items():
        if isinstance(profile, dict) and "history_learning_policy" in profile:
            scoped = validate_history_policy(profile["history_learning_policy"])
            if (scoped["required"] or scoped.get("vocabulary_rules")) and (not isinstance(article_id, str) or not article_id.strip()):
                raise ValueError("記事別履歴policyにはarticle-idが必要です")
            if key == article_id:
                policies.append(scoped)
    if not policies:
        return None
    result = {"schema": "nps-history-learning-policy/v1",
              "required": any(policy["required"] for policy in policies)}
    rows, ids = [], set()
    for policy in policies:
        for row in policy.get("required_sources", []):
            if row["id"] in ids:
                raise ValueError("全体と記事別のhistory source IDが重複しています")
            ids.add(row["id"])
            rows.append(dict(row))
    if rows:
        result["required_sources"] = rows
    rules, ids = [], set()
    for policy in policies:
        for rule in policy.get("vocabulary_rules", []):
            if rule["id"] in ids:
                raise ValueError("全体と記事別のvocabulary rule IDが重複しています")
            ids.add(rule["id"])
            rules.append(rule)
    if rules:
        result["vocabulary_rules"] = rules
    return result


def _history_quote(text: str, row: dict) -> str:
    """JSON履歴は明示pointerで原文を選ぶ。意味の分類や本文の生成はしない。"""
    if "json_pointer" not in row:
        return text
    pointer = row["json_pointer"]
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("history JSON pointerが不正です")
    value = json.loads(text)
    try:
        for token in pointer.split("/")[1:]:
            key = token.replace("~1", "/").replace("~0", "~")
            if isinstance(value, list):
                if not key.isdecimal():
                    raise ValueError("history JSON pointerが不正です")
                value = value[int(key)]
            elif isinstance(value, dict):
                value = value[key]
            else:
                raise ValueError("history JSON pointerが不正です")
    except (KeyError, IndexError) as exc:
        raise ValueError("history JSON pointerを読めません") from exc
    if not isinstance(value, str):
        raise ValueError("history JSON pointerは原文文字列を指定してください")
    return value


def read_history_sources(evidence: Path, reference_hashes: dict[str, str], *,
                         required_sources: list[dict] | None = None,
                         initial_capture: InputCapture | None = None) -> dict:
    """styleの許可参照から原文引用を実読取りする。抽出は候補のまま返す。"""
    parse_json = _load_sibling_module("note_footer_selection").parse_json
    initial_capture = initial_capture if initial_capture is not None else ({}, {})
    evidence_actual = evidence.resolve(strict=True)
    remember_input_path(initial_capture, evidence, evidence_actual)
    raw = evidence_actual.read_bytes()
    remember_input_bytes(initial_capture, evidence_actual, raw)
    data = parse_json(raw.decode("utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != "note-authorship-evidence/v1":
        raise ValueError("history evidence schemaが不正です")
    learning = data.get("history_learning")
    sources = learning.get("sources") if isinstance(learning, dict) else None
    if not isinstance(sources, list) or not sources:
        raise ValueError("history sourcesが必要です")
    for required in required_sources or []:
        matched = [row for row in sources if isinstance(row, dict) and row.get("id") == required["id"]]
        if (len(matched) != 1
                or any(matched[0].get(key) != required.get(key)
                       for key in ("quote", "evidence_ref", "json_pointer"))
                or not isinstance(matched[0].get("path"), str) or not matched[0]["path"].strip()):
            raise ValueError("必須history sourceが欠落または宣言と不一致です")
        selected = evidence_actual.parent / matched[0]["path"]
        declared = evidence_actual.parent / required["path"]
        selected_actual = selected.resolve(strict=True)
        declared_actual = declared.resolve(strict=True)
        remember_input_path(initial_capture, selected, selected_actual)
        remember_input_path(initial_capture, declared, declared_actual)
        if selected_actual != declared_actual:
            raise ValueError("必須history sourceの参照先が宣言と不一致です")
    captured, checked, ids = {}, [], set()
    for row in sources:
        if (not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k].strip()
                for k in ("id", "path", "sha256", "quote", "evidence_ref")) or row["id"] in ids):
            raise ValueError("history sourceの根拠が不足または重複しています")
        # Persisted source paths are relative to the evidence document.
        # Absolute legacy inputs still resolve through the same allowlist.
        path = evidence_actual.parent / row["path"]
        resolved = path.resolve(strict=True)
        remember_input_path(initial_capture, path, resolved)
        if not path.is_absolute() or str(resolved) not in reference_hashes:
            raise ValueError("history sourceがstyleの許可参照にありません")
        value = resolved.read_bytes()
        remember_input_bytes(initial_capture, resolved, value)
        if digest(value) != row["sha256"] or digest(value) != reference_hashes[str(resolved)]:
            raise ValueError("history source hashが一致しません")
        if row["quote"] not in _history_quote(value.decode("utf-8"), row):
            raise ValueError("history quoteが保存原文にありません")
        ids.add(row["id"])
        if path in captured and captured[path] != (resolved, value):
            raise ValueError("history sourceが読取り中に変更されました")
        captured[path] = (resolved, value)
        checked.append({key: row[key] for key in ("id", "path", "sha256", "quote", "evidence_ref")}
                       | {"kind": "candidate", "quote_sha256": digest(row["quote"].encode("utf-8"))})
    for path, (resolved, value) in captured.items():
        if path.resolve(strict=True) != resolved or resolved.read_bytes() != value:
            raise ValueError("history sourceが読取り中に変更されました")
    if evidence.resolve(strict=True) != evidence_actual or evidence_actual.read_bytes() != raw:
        raise ValueError("history evidenceが読取り中に変更されました")
    check_input_capture(initial_capture)
    return {"status": "candidate_sources_verified", "sources": checked,
            "evidence_sha256": digest(raw), "draft_sha256": data.get("draft_sha256"),
            "semantic_understanding_verified": False,
            "human_adoption_verified": False, "publication_allowed": False}


def history_readback(settings: Path, article_id: str, evidence: Path | None) -> dict:
    """新稿の存在を要求せず、制作前の既存履歴を回収する。"""
    read_workspace_settings = _load_sibling_module("note_workflow_gate").read_workspace_settings
    initial_capture = ({}, {})
    settings_actual = settings.resolve(strict=True)
    remember_input_path(initial_capture, settings, settings_actual)
    expected, dirs = read_workspace_settings(settings_actual, article_id, initial_capture=initial_capture)
    if not expected.get("history_learning_policy", {}).get("required"):
        if (settings.resolve(strict=True) != settings_actual
                or digest(settings_actual.read_bytes()) != expected["settings_sha256"]):
            raise ValueError("history読取り中にsettingsが変更されました")
        check_input_capture(initial_capture)
        return {"status": "not_required", "human_adoption_verified": False,
                "article_id": article_id, "settings_readback": expected,
                "storage": {key: str(path) for key, path in dirs.items()}}
    if evidence is None:
        raise ValueError("history evidenceが必要です")
    result = read_history_sources(evidence, expected["reference_hashes"],
                                  required_sources=expected["history_learning_policy"].get("required_sources"),
                                  initial_capture=initial_capture)
    if (settings.resolve(strict=True) != settings_actual
            or read_workspace_settings(settings_actual, article_id, initial_capture=initial_capture) != (expected, dirs)):
        raise ValueError("history読取り中にsettingsが変更されました")
    check_input_capture(initial_capture)
    return {**result, "article_id": article_id, "settings_readback": expected,
            "storage": {key: str(path) for key, path in dirs.items()}}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def article_directory(dirs: dict[str, Path], article_id: str) -> Path:
    if (not isinstance(article_id, str) or not article_id.strip()
            or article_id in {".", ".."} or "/" in article_id or "\\" in article_id):
        raise ValueError("記事IDを外部履歴のフォルダ名として解決できません")
    root = dirs["feedback"].resolve()
    target = (root / article_id).resolve()
    if not target.is_relative_to(root):
        raise ValueError("記事別履歴が指定feedback保存先の外にあります")
    return target


def review_entries(entries: Any) -> None:
    if not isinstance(entries, list):
        raise ValueError("採用履歴は配列が必要です")
    for entry in entries:
        if (not isinstance(entry, dict) or not isinstance(entry.get("origin"), str)
                or entry["origin"] not in {"author", "ai"}):
            raise ValueError("履歴の由来が不正です")
        if (not isinstance(entry.get("decision"), str)
                or entry["decision"] not in {"adopted", "rejected", "pending", "source_preserved"}):
            raise ValueError("採否が不足または不正です")
        if entry.get("decision") == "source_preserved" and entry.get("origin") != "author":
            raise ValueError("AI案を本人原文として保存できません")
        if any(not isinstance(entry.get(key), str) for key in ("before", "after")):
            raise ValueError("履歴の変更前後が必要です")
        if any(not isinstance(entry.get(key), str) or not entry[key].strip()
               for key in ("reason", "evidence_ref")):
            raise ValueError("採否の理由と根拠が必要です")


def diff_bytes(prior: bytes, current: bytes) -> bytes:
    return ("# 本人原稿と編集稿の差分\n\n" + "".join(difflib.unified_diff(
        prior.decode("utf-8").splitlines(keepends=True),
        current.decode("utf-8").splitlines(keepends=True),
        fromfile="previous-local", tofile="current-draft")) + "\n").encode("utf-8")


def confined(base: Path, *parts: str) -> Path:
    path = base.joinpath(*parts)
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError("履歴内のsymlinkが記事別feedback保存先の外を参照しています")
    return path


def record_feedback(dirs: dict[str, Path], article_id: str, source: Path, draft: Path,
                    prior: Path, entries: list[dict], *, conversation_id: str,
                    allow_empty_working_drafts: bool = False) -> dict:
    """trusted runtimeが採否根拠を供給する。承認receiptを発行する機能ではない。"""
    review_entries(entries)
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("採用履歴の会話が必要です")
    for path, owner in ((source, "sources"), (prior, "sources"), (draft, "drafts")):
        if not path.resolve().is_relative_to(dirs[owner].resolve()):
            raise ValueError("原資料または原稿が指定保存先の外にあります")
    values = {"source": source.read_bytes(), "draft": draft.read_bytes(), "prior": prior.read_bytes()}
    if not values["source"].strip() or (not allow_empty_working_drafts
            and any(not values[key].strip() for key in ("draft", "prior"))):
        raise ValueError("原資料・原稿は空にできません")
    for value in values.values():
        value.decode("utf-8")
    base = article_directory(dirs, article_id)
    base.mkdir(parents=True, exist_ok=True)
    snapshots = confined(base, "snapshots")
    old = confined(base, "feedback.json")
    difference_path = confined(base, "note-vs-local-diff.md")
    history = confined(base, "history")
    snapshots.mkdir(exist_ok=True)
    record = {"schema_version": SCHEMA, "article_id": article_id,
              "conversation_id": conversation_id, "recorded_at": datetime.now().astimezone().isoformat(),
              "entries": entries, "snapshot_hashes": {key: digest(value) for key, value in values.items()}}
    for key, value in values.items():
        path = confined(base, "snapshots", record["snapshot_hashes"][key] + ".txt")
        if path.exists():
            if path.read_bytes() != value:
                raise ValueError("保存済みsnapshotの内容が一致しません")
        else:
            path.write_bytes(value)
    difference = diff_bytes(values["prior"], values["draft"])
    record["diff_sha256"] = digest(difference)
    # 更新前の履歴・差分を保全。原稿の唯一の正本は利用者のdraftのまま。
    if old.exists():
        history.mkdir(exist_ok=True)
        old_bytes = old.read_bytes()
        confined(base, "history", digest(old_bytes) + ".json").write_bytes(old_bytes)
        old_diff = difference_path
        if old_diff.exists():
            old_diff_bytes = old_diff.read_bytes()
            confined(base, "history", digest(old_diff_bytes) + ".md").write_bytes(old_diff_bytes)
    difference_path.write_bytes(difference)
    old.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return read_article_feedback(dirs, article_id, source, draft)


def _verified_feedback(dirs: dict[str, Path], article_id: str, *,
                       captured_paths: dict[str, str] | None = None,
                       initial_capture: InputCapture | None = None) -> tuple[dict, dict]:
    """既存履歴とsnapshot・差分の実体を同じ検査で読み戻す。"""
    base = article_directory(dirs, article_id)
    initial_capture = initial_capture if initial_capture is not None else ({}, {})
    selected_inputs = {}
    input_bytes = {}

    def capture(*parts: str) -> bytes:
        selected = str(base.joinpath(*parts))
        resolved = confined(base, *parts).resolve(strict=True)
        if not resolved.is_relative_to(base):
            raise ValueError("feedback実体が記事別保存先の外です")
        remember_input_path(initial_capture, Path(selected), resolved)
        if selected_inputs.setdefault(selected, str(resolved)) != str(resolved):
            raise ValueError("feedback入力pathが読取り中に変更されました")
        value = resolved.read_bytes()
        remember_input_bytes(initial_capture, resolved, value)
        if input_bytes.setdefault(str(resolved), value) != value:
            raise ValueError("feedback入力が読取り中に変更されました")
        return value

    raw = capture("feedback.json")
    record = json.loads(raw)
    if not isinstance(record, dict) or record.get("schema_version") != SCHEMA or record.get("article_id") != article_id:
        raise ValueError("別記事または不正なfeedback履歴です")
    if not isinstance(record.get("recorded_at"), str):
        raise ValueError("履歴の日時が不足または不正です")
    stamp = datetime.fromisoformat(record["recorded_at"])
    if stamp.utcoffset() is None or not isinstance(record.get("conversation_id"), str) or not record["conversation_id"].strip():
        raise ValueError("履歴の日時・由来会話が不正です")
    review_entries(record.get("entries"))
    hashes = record.get("snapshot_hashes")
    if not isinstance(hashes, dict) or set(hashes) != {"source", "draft", "prior"}:
        raise ValueError("履歴snapshotが不足しています")
    snapshots = {}
    for key, sha in hashes.items():
        if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("履歴snapshot hashが不正です")
        value = capture("snapshots", sha + ".txt")
        if digest(value) != sha:
            raise ValueError("履歴snapshotが変更されています")
        snapshots[key] = value
    difference = capture("note-vs-local-diff.md")
    if digest(difference) != record.get("diff_sha256") or difference != diff_bytes(snapshots["prior"], snapshots["draft"]):
        raise ValueError("差分記録がsnapshotと一致しません")
    if (any(str(Path(selected).resolve(strict=True)) != resolved for selected, resolved in selected_inputs.items())
            or any(Path(path).read_bytes() != value for path, value in input_bytes.items())):
        raise ValueError("feedback入力が読取り中に変更されました")
    if captured_paths is not None:
        for selected, resolved in selected_inputs.items():
            if captured_paths.setdefault(selected, resolved) != resolved:
                raise ValueError("feedback入力の初回pathが変更されています")
    check_input_capture(initial_capture)
    return record, {"record_sha256": digest(raw), "diff_sha256": digest(difference), "snapshot_hashes": hashes}



def read_feedback_record(dirs: dict[str, Path], article_id: str, *,
                         captured_paths: dict[str, str] | None = None,
                         initial_capture: InputCapture | None = None) -> tuple[dict, dict]:
    return _verified_feedback(dirs, article_id, captured_paths=captured_paths, initial_capture=initial_capture)


def read_article_feedback(dirs: dict[str, Path], article_id: str, source: Path, draft: Path, *,
                          captured_paths: dict[str, str] | None = None,
                          initial_capture: InputCapture | None = None) -> dict:
    """保存先をpacketから受け取らず、設定から独立に解決して読み直す。"""
    for path, owner in ((source, "sources"), (draft, "drafts")):
        if not path.resolve().is_relative_to(dirs[owner].resolve()):
            raise ValueError("原資料または原稿が指定保存先の外にあります")
    _, readback = _verified_feedback(dirs, article_id, captured_paths=captured_paths, initial_capture=initial_capture)
    hashes = readback["snapshot_hashes"]
    if digest(source.read_bytes()) != hashes["source"] or digest(draft.read_bytes()) != hashes["draft"]:
        raise ValueError("履歴が現在の原資料・原稿と一致しません")
    return readback


def readback(settings: Path, article_id: str, source: Path, draft: Path) -> dict:
    """原稿制作前に読む実内容を返す。読取りは理解・採用・公開承認の証明ではない。"""
    read_workspace_settings = _load_sibling_module("note_workflow_gate").read_workspace_settings
    initial_capture = ({}, {})
    selected_inputs = {path: path.resolve(strict=True) for path in (settings, source, draft)}
    for path, resolved in selected_inputs.items():
        remember_input_path(initial_capture, path, resolved)
    settings_actual, source_actual, draft_actual = (selected_inputs[path] for path in (settings, source, draft))
    expected, dirs = read_workspace_settings(settings_actual, article_id, initial_capture=initial_capture)
    feedback_paths = {}
    feedback = read_article_feedback(dirs, article_id, source_actual, draft_actual,
                                     captured_paths=feedback_paths, initial_capture=initial_capture)
    captured: dict[Path, tuple[Path, bytes]] = {}

    def capture(path: Path, sha: str) -> dict:
        resolved = path.resolve()
        remember_input_path(initial_capture, path, resolved)
        data = resolved.read_bytes()
        remember_input_bytes(initial_capture, resolved, data)
        if digest(data) != sha:
            raise ValueError("読取り中に内容が変更されています")
        content = data.decode("utf-8")
        captured[path] = (resolved, data)
        return {"path": str(resolved), "sha256": sha, "content": content}

    settings_content = capture(settings_actual, expected["settings_sha256"])
    references = [capture(Path(path), sha) for path, sha in expected["reference_hashes"].items()]
    base = article_directory(dirs, article_id)
    record_content = capture(Path(feedback_paths[str(base / "feedback.json")]), feedback["record_sha256"])
    difference = capture(Path(feedback_paths[str(base / "note-vs-local-diff.md")]), feedback["diff_sha256"])
    source_content = capture(source_actual, feedback["snapshot_hashes"]["source"])
    draft_content = capture(draft_actual, feedback["snapshot_hashes"]["draft"])
    # snapshotも再読対象に含め、検証後の改変を取りこぼさない。
    for sha in feedback["snapshot_hashes"].values():
        capture(Path(feedback_paths[str(base / "snapshots" / (sha + ".txt"))]), sha)
    if read_workspace_settings(settings_actual, article_id, initial_capture=initial_capture) != (expected, dirs):
        raise ValueError("読取り中に設定または文体参照が変更されています")
    if read_article_feedback(dirs, article_id, source_actual, draft_actual, initial_capture=initial_capture) != feedback:
        raise ValueError("読取り中にfeedback履歴が変更されています")
    for path, (resolved, data) in captured.items():
        if path.resolve() != resolved or path.read_bytes() != data:
            raise ValueError("検証した内容と返却する内容が一致しません")
    if any(path.resolve(strict=True) != resolved for path, resolved in selected_inputs.items()):
        raise ValueError("制作入力の選択経路が読取り中に変更されました")
    if any(str(Path(selected).resolve(strict=True)) != resolved for selected, resolved in feedback_paths.items()):
        raise ValueError("feedbackの選択経路が読取り中に変更されました")
    check_input_capture(initial_capture)
    return {"status": "readback", "article_id": article_id,
            "workspace_settings": settings_content, "settings_readback": expected,
            "style_references": references, "source": source_content, "draft": draft_content,
            "feedback_readback": feedback,
            "feedback": {"record": json.loads(record_content["content"]),
                         "record_file": record_content, "diff": difference},
            "semantic_understanding_verified": False, "human_adoption_verified": False,
            "publication_allowed": False,
            "notice": "制作前にこの実内容を読んでください。読取りは意味理解・本人採用・公開許可を証明しません。"}


def main() -> int:
    parser = argparse.ArgumentParser(description="本人の採否履歴を外部SSOTへ保全する（公開操作なし）")
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--article-id", required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--draft", type=Path)
    parser.add_argument("--history-only", action="store_true", help="新稿作成前の履歴候補だけを読取り")
    parser.add_argument("--history-evidence", type=Path, help="既存authorship証拠のhistory_learning.sources")
    parser.add_argument("--readback", action="store_true", help="現在の文体参照と記事別履歴の実内容を読取り専用で返す")
    parser.add_argument("--prior-draft", type=Path)
    parser.add_argument("--entries", type=Path)
    parser.add_argument("--conversation-id")
    args = parser.parse_args()
    if args.history_only and (not args.readback or args.source or args.draft):
        parser.error("--history-onlyは--readbackと使い、--source/--draftは指定しません")
    if not args.history_only and (args.source is None or args.draft is None):
        parser.error("--sourceと--draftが必要です")
    if args.history_evidence and not args.history_only:
        parser.error("--history-evidenceには--history-onlyが必要です")
    write_fields = (args.prior_draft, args.entries, args.conversation_id)
    if args.readback and any(value is not None for value in write_fields):
        parser.error("--readbackに--prior-draft/--entries/--conversation-idは指定できません")
    if not args.readback and any(value is None for value in write_fields):
        parser.error("保存には--prior-draft/--entries/--conversation-idが必要です")
    read_workspace_settings = _load_sibling_module("note_workflow_gate").read_workspace_settings
    try:
        if args.history_only:
            print(json.dumps(history_readback(args.settings, args.article_id, args.history_evidence), ensure_ascii=True))
            return 0
        if args.readback:
            result = readback(args.settings, args.article_id, args.source, args.draft)
            print(json.dumps(result, ensure_ascii=True))
            return 0
        _, dirs = read_workspace_settings(args.settings, args.article_id)
        result = record_feedback(dirs, args.article_id, args.source, args.draft, args.prior_draft,
                                 json.loads(args.entries.read_text(encoding="utf-8")), conversation_id=args.conversation_id)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=True))
        return 1
    print(json.dumps({"status": "recorded", "feedback_readback": result}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
