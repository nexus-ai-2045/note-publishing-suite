#!/usr/bin/env python3
"""記事別の採用履歴を外部SSOTに保存し、次の入口で現稿との一致を検査する。"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = "nps-article-feedback/v1"


def validate_history_policy(value: Any) -> dict:
    if (not isinstance(value, dict) or value.get("schema") != "nps-history-learning-policy/v1"
            or type(value.get("required")) is not bool):
        raise ValueError("history_learning_policyが不正です")
    return {"schema": value["schema"], "required": value["required"]}


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


def read_history_sources(evidence: Path, reference_hashes: dict[str, str]) -> dict:
    """styleの許可参照から原文引用を実読取りする。抽出は候補のまま返す。"""
    from note_footer_selection import parse_json
    raw = evidence.read_bytes()
    data = parse_json(raw.decode("utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != "note-authorship-evidence/v1":
        raise ValueError("history evidence schemaが不正です")
    learning = data.get("history_learning")
    sources = learning.get("sources") if isinstance(learning, dict) else None
    if not isinstance(sources, list) or not sources:
        raise ValueError("history sourcesが必要です")
    captured, checked, ids = {}, [], set()
    for row in sources:
        if (not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k].strip()
                for k in ("id", "path", "sha256", "quote", "evidence_ref")) or row["id"] in ids):
            raise ValueError("history sourceの根拠が不足または重複しています")
        path = Path(row["path"])
        if not path.is_absolute() or str(path.resolve()) not in reference_hashes:
            raise ValueError("history sourceがstyleの許可参照にありません")
        value = path.read_bytes()
        if digest(value) != row["sha256"] or digest(value) != reference_hashes[str(path.resolve())]:
            raise ValueError("history source hashが一致しません")
        if row["quote"] not in _history_quote(value.decode("utf-8"), row):
            raise ValueError("history quoteが保存原文にありません")
        ids.add(row["id"])
        captured[path] = (path.resolve(), value)
        checked.append({key: row[key] for key in ("id", "path", "sha256", "quote", "evidence_ref")}
                       | {"kind": "candidate", "quote_sha256": digest(row["quote"].encode("utf-8"))})
    for path, (resolved, value) in captured.items():
        if path.resolve() != resolved or path.read_bytes() != value:
            raise ValueError("history sourceが読取り中に変更されました")
    if evidence.read_bytes() != raw:
        raise ValueError("history evidenceが読取り中に変更されました")
    return {"status": "candidate_sources_verified", "sources": checked,
            "evidence_sha256": digest(raw), "semantic_understanding_verified": False,
            "human_adoption_verified": False, "publication_allowed": False}


def history_readback(settings: Path, article_id: str, evidence: Path | None) -> dict:
    """新稿の存在を要求せず、制作前の既存履歴を回収する。"""
    from note_workflow_gate import read_workspace_settings
    expected, dirs = read_workspace_settings(settings, article_id)
    if not expected.get("history_learning_policy", {}).get("required"):
        return {"status": "not_required", "human_adoption_verified": False}
    if evidence is None:
        raise ValueError("history evidenceが必要です")
    result = read_history_sources(evidence, expected["reference_hashes"])
    if read_workspace_settings(settings, article_id) != (expected, dirs):
        raise ValueError("history読取り中にsettingsが変更されました")
    return {**result, "article_id": article_id, "settings_readback": expected}


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
                    prior: Path, entries: list[dict], *, conversation_id: str) -> dict:
    """trusted runtimeが採否根拠を供給する。承認receiptを発行する機能ではない。"""
    review_entries(entries)
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("採用履歴の会話が必要です")
    for path, owner in ((source, "sources"), (prior, "sources"), (draft, "drafts")):
        if not path.resolve().is_relative_to(dirs[owner].resolve()):
            raise ValueError("原資料または原稿が指定保存先の外にあります")
    values = {"source": source.read_bytes(), "draft": draft.read_bytes(), "prior": prior.read_bytes()}
    if any(not value.strip() for value in values.values()):
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


def _verified_feedback(dirs: dict[str, Path], article_id: str) -> tuple[dict, dict]:
    """既存履歴とsnapshot・差分の実体を同じ検査で読み戻す。"""
    base = article_directory(dirs, article_id)
    raw = confined(base, "feedback.json").read_bytes()
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
        value = confined(base, "snapshots", sha + ".txt").read_bytes()
        if digest(value) != sha:
            raise ValueError("履歴snapshotが変更されています")
        snapshots[key] = value
    difference = confined(base, "note-vs-local-diff.md").read_bytes()
    if digest(difference) != record.get("diff_sha256") or difference != diff_bytes(snapshots["prior"], snapshots["draft"]):
        raise ValueError("差分記録がsnapshotと一致しません")
    return record, {"record_sha256": digest(raw), "diff_sha256": digest(difference), "snapshot_hashes": hashes}



def read_feedback_record(dirs: dict[str, Path], article_id: str) -> tuple[dict, dict]:
    return _verified_feedback(dirs, article_id)


def read_article_feedback(dirs: dict[str, Path], article_id: str, source: Path, draft: Path) -> dict:
    """保存先をpacketから受け取らず、設定から独立に解決して読み直す。"""
    for path, owner in ((source, "sources"), (draft, "drafts")):
        if not path.resolve().is_relative_to(dirs[owner].resolve()):
            raise ValueError("原資料または原稿が指定保存先の外にあります")
    _, readback = _verified_feedback(dirs, article_id)
    hashes = readback["snapshot_hashes"]
    if digest(source.read_bytes()) != hashes["source"] or digest(draft.read_bytes()) != hashes["draft"]:
        raise ValueError("履歴が現在の原資料・原稿と一致しません")
    return readback


def readback(settings: Path, article_id: str, source: Path, draft: Path) -> dict:
    """原稿制作前に読む実内容を返す。読取りは理解・採用・公開承認の証明ではない。"""
    from note_workflow_gate import read_workspace_settings
    expected, dirs = read_workspace_settings(settings, article_id)
    feedback = read_article_feedback(dirs, article_id, source, draft)
    captured: dict[Path, tuple[Path, bytes]] = {}

    def capture(path: Path, sha: str) -> dict:
        resolved = path.resolve()
        data = path.read_bytes()
        if digest(data) != sha:
            raise ValueError("読取り中に内容が変更されています")
        content = data.decode("utf-8")
        captured[path] = (resolved, data)
        return {"path": str(resolved), "sha256": sha, "content": content}

    settings_content = capture(settings, expected["settings_sha256"])
    references = [capture(Path(path), sha) for path, sha in expected["reference_hashes"].items()]
    base = article_directory(dirs, article_id)
    record_content = capture(confined(base, "feedback.json"), feedback["record_sha256"])
    difference = capture(confined(base, "note-vs-local-diff.md"), feedback["diff_sha256"])
    source_content = capture(source, feedback["snapshot_hashes"]["source"])
    draft_content = capture(draft, feedback["snapshot_hashes"]["draft"])
    # snapshotも再読対象に含め、検証後の改変を取りこぼさない。
    for sha in feedback["snapshot_hashes"].values():
        capture(confined(base, "snapshots", sha + ".txt"), sha)
    if read_workspace_settings(settings, article_id) != (expected, dirs):
        raise ValueError("読取り中に設定または文体参照が変更されています")
    if read_article_feedback(dirs, article_id, source, draft) != feedback:
        raise ValueError("読取り中にfeedback履歴が変更されています")
    for path, (resolved, data) in captured.items():
        if path.resolve() != resolved or path.read_bytes() != data:
            raise ValueError("検証した内容と返却する内容が一致しません")
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
    from note_workflow_gate import read_workspace_settings
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
