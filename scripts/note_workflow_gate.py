#!/usr/bin/env python3
"""読取り専用の承認照合。receipt の発行と真正性の担保は trusted runtime の責務。"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
_LOADER_SPEC = importlib.util.spec_from_file_location(
    "_nps_loader_bootstrap", Path(__file__).with_name("nps_script_loader.py"))
if _LOADER_SPEC is None or _LOADER_SPEC.loader is None:
    raise ImportError("cannot load NPS script loader")
_LOADER_MODULE = importlib.util.module_from_spec(_LOADER_SPEC)
_LOADER_SPEC.loader.exec_module(_LOADER_MODULE)
_load_sibling_module = _LOADER_MODULE.load_script

_FEEDBACK_MODULE = _load_sibling_module("note_feedback")
InputCapture = _FEEDBACK_MODULE.InputCapture
check_input_capture = _FEEDBACK_MODULE.check_input_capture
remember_input_bytes = _FEEDBACK_MODULE.remember_input_bytes
remember_input_path = _FEEDBACK_MODULE.remember_input_path

SCHEMA = "note-workflow-review/v1"
ROUTES = {"direct_draft", "source_article", "collaborative"}
STAGES = {"edit", "research", "layout", "settings", "publish"}
AUTHENTICITY = "ローカルJSONは承認の真正性を暗号学的に証明しません。trusted runtime が人間の承認receiptを管理します。"


def canonical_sha256(value: Any) -> str:
    """UTF-8、キー順、空白なしのJSONをハッシュする。"""
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def read_workspace_settings(settings_path: Path | None, article_id: str, *,
                            initial_capture: InputCapture | None = None) -> tuple[dict, dict[str, Path]]:
    """利用のたびに外部設定と文体参照を読み直す。書込みや既定設定作成はしない。"""
    if settings_path is None:
        raise ValueError("外部settingsの指定が必要です")
    initial_capture = initial_capture if initial_capture is not None else ({}, {})
    config_path = Path(settings_path).resolve()
    remember_input_path(initial_capture, Path(settings_path), config_path)
    captured_paths = {Path(settings_path).absolute(): config_path}
    if config_path.is_relative_to(PACKAGE_ROOT):
        raise ValueError("settingsはNPS package外に置く必要があります")
    raw = config_path.read_bytes()
    remember_input_bytes(initial_capture, config_path, raw)
    captured_bytes = {config_path: raw}
    config = parse_packet(raw)
    if not isinstance(config, dict) or config.get("schema_version") != "nps-workspace-settings/v1":
        raise ValueError("外部settingsのschema_versionが不正です")

    def resolve_path(value: Any, base: Path) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("設定パスが不足または不正です")
        candidate = Path(value)
        selected = (candidate if candidate.is_absolute() else base / candidate).absolute()
        path = selected.resolve()
        remember_input_path(initial_capture, selected, path)
        if captured_paths.setdefault(selected, path) != path:
            raise ValueError("設定pathが読取り中に変更されました")
        if path.is_relative_to(PACKAGE_ROOT):
            raise ValueError("設定・保存先・文体参照はNPS package外に置く必要があります")
        return path

    workspace = resolve_path(config.get("workspace_root"), config_path.parent)
    storage = config.get("storage")
    style = config.get("style")
    if not isinstance(storage, dict) or not isinstance(style, dict):
        raise ValueError("storageとstyleが必要です")
    dirs = {key: resolve_path(storage.get(key), workspace) for key in ("drafts", "sources", "feedback")}
    for key in ("assets", "ledgers"):
        if key in storage:
            dirs[key] = resolve_path(storage[key], workspace)
    if any(path.exists() and not path.is_dir() for path in dirs.values()):
        raise ValueError("storageの保存先はディレクトリである必要があります")
    default = resolve_path(style.get("default_profile"), workspace)
    profiles = style.get("article_profiles")
    if not isinstance(profiles, dict) or any(not isinstance(key, str) for key in profiles):
        raise ValueError("article_profilesが不正です")
    normalized_profiles = {}
    for key, profile in profiles.items():
        values = profile.get("references") if isinstance(profile, dict) else profile
        if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("article_profilesの参照path配列が不正です")
        normalized_profiles[key] = values
    article_history_policy = _load_sibling_module("note_feedback").article_history_policy
    history_policy = article_history_policy(style, article_id)
    if history_policy and history_policy["required"] and not normalized_profiles.get(article_id):
        raise ValueError("履歴必須の記事IDには空でない明示profileが必要です")
    profile_refs = [resolve_path(value, workspace) for value in normalized_profiles.get(article_id, [])]
    refs = [default] + profile_refs
    tag_reference_policy = config.get("tag_reference_policy")
    if "tag_reference_policy" in config:
        validate_policy = _load_sibling_module("note_editor_prepublish_verify").validate_tag_reference_policy
        if errors := validate_policy(tag_reference_policy):
            raise ValueError("タグ参照policyが不正です: " + "; ".join(errors))
        tag_reference_policy = dict(tag_reference_policy)
        tag_reference_policy["strategy_sources"] = {
            axis: [str(resolve_path(value, workspace)) for value in values]
            for axis, values in tag_reference_policy.get("strategy_sources", {}).items()}
        if tag_reference_policy["required"]:
            refs.extend(Path(value) for values in tag_reference_policy["strategy_sources"].values()
                        for value in values)
    reference_hashes = {}
    for path in refs:
        data = path.read_bytes()
        remember_input_bytes(initial_capture, path, data)
        if captured_bytes.setdefault(path, data) != data:
            raise ValueError("文体参照が読取り中に変更されました")
        if not data.strip():
            raise ValueError("文体参照が空です")
        reference_hashes[str(path)] = hashlib.sha256(data).hexdigest()
    expected = {"settings_sha256": hashlib.sha256(raw).hexdigest(), "reference_hashes": reference_hashes}
    if "tag_reference_policy" in config:
        expected["tag_reference_policy"] = tag_reference_policy
    if "tag_count_policy" in config:
        count_policy = config["tag_count_policy"]
        validate_count = _load_sibling_module("note_editor_prepublish_verify").validate_tag_count_policy
        if errors := validate_count(count_policy):
            raise ValueError("タグ件数policyが不正です: " + "; ".join(errors))
        expected["tag_count_policy"] = dict(count_policy)
    linebreak_policy = _load_sibling_module("note_linebreak_gate").resolve_policy(style, article_id, require_article_id=True)
    if linebreak_policy is not None:
        expected["linebreak_policy"] = linebreak_policy
    if history_policy is not None:
        selected_profile = profiles.get(article_id)
        scoped_policy = selected_profile.get("history_learning_policy", {}) if isinstance(selected_profile, dict) else {}
        scoped_ids = {row["id"] for row in scoped_policy.get("required_sources", [])}
        for row in history_policy.get("required_sources", []):
            row["path"] = str(resolve_path(row["path"], workspace))
            if row["path"] not in reference_hashes:
                raise ValueError("required_sourcesはstyle許可参照から指定してください")
            if row["id"] in scoped_ids and Path(row["path"]) not in profile_refs:
                raise ValueError("記事別required_sourcesは選択記事のreferencesから指定してください")
        expected["history_learning_policy"] = history_policy
    profile = profiles.get(article_id)
    fidelity = (profile.get("conversation_fidelity_policy") if isinstance(profile, dict) else None)
    global_fidelity = config.get("conversation_fidelity_policy")
    if fidelity is None:
        fidelity = global_fidelity
    elif global_fidelity is not None:
        if not isinstance(global_fidelity, dict):
            raise ValueError("会話忠実性global policy不正")
        if not isinstance(fidelity, dict):
            raise ValueError("会話忠実性article policy不正")
        fidelity = {**global_fidelity, **fidelity,
                    "required": global_fidelity.get("required") is True or fidelity.get("required") is True}
    if fidelity is not None:
        if (not isinstance(fidelity, dict)
                or fidelity.get("schema") != "note-conversation-fidelity-policy/v1"
                or type(fidelity.get("required")) is not bool):
            raise ValueError("会話忠実性policyが不正です")
        fidelity = dict(fidelity)
        if fidelity["required"]:
            source = resolve_path(fidelity.get("source"), workspace)
            if not source.is_relative_to(dirs["sources"]):
                raise ValueError("会話原資料がsources保存先の外です")
            source_raw = source.read_bytes()
            remember_input_bytes(initial_capture, source, source_raw)
            if hashlib.sha256(source_raw).hexdigest() != fidelity.get("sha256"):
                raise ValueError("会話原資料のhashが不一致です")
            fidelity["source"] = str(source)
        expected["conversation_fidelity_policy"] = fidelity
    for policy_key, module in (("publication_drafts_policy", "note_publication_drafts"),
                               ("footer_readback_policy", "note_footer_selection")):
        selected = profile.get(policy_key) if isinstance(profile, dict) and policy_key in profile else config.get(policy_key)
        if selected is not None or policy_key in config or isinstance(profile, dict) and policy_key in profile:
            expected[policy_key] = _load_sibling_module(module).validate_policy(selected)
    if "research_quality_policy" in config:
        validate_policy = _load_sibling_module("note_research_quality").validate_policy
        expected["research_quality_policy"] = validate_policy(config["research_quality_policy"])
    if (any(selected.resolve() != resolved for selected, resolved in captured_paths.items())
            or any(path.read_bytes() != value for path, value in captured_bytes.items())):
        raise ValueError("設定または文体参照が読取り中に変更されました")
    check_input_capture(initial_capture)
    return expected, dirs


def validate_layout(layout: Any) -> bool:
    """全レイアウト項目の採否と提案・対話・決定の参照を承認対象にする。"""
    if not isinstance(layout, dict):
        return False
    for key in ("cover", "toc", "footer_cards", "illustrations", "embeds", "hyperlinks"):
        item = layout.get(key)
        if not isinstance(item, dict) or item.get("decision") not in ("include", "omit"):
            return False
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            return False
    review = layout.get("review")
    if not isinstance(review, dict):
        return False
    unresolved_refs = {"pending", "unknown", "todo", "tbd", "none", "null", "n/a",
                       "未確認", "未定", "保留", "確認待ち", "未決定", "未承認", "検討中"}
    for key in ("proposal_ref", "discussion_ref", "decision_ref"):
        ref = review.get(key)
        if not isinstance(ref, str) or not ref.strip() or ref.strip().casefold() in unresolved_refs:
            return False
    for key in ("illustrations", "embeds", "hyperlinks"):
        choice = layout[key]
        items = choice.get("items")
        if not isinstance(items, list):
            return False
        if choice["decision"] == "omit":
            if items:
                return False
            continue
        if not items:
            return False
        source_key = "source_ref" if key == "illustrations" else "url"
        for item in items:
            if not isinstance(item, dict) or any(
                    not isinstance(item.get(field), str) or not item[field].strip()
                    for field in ("purpose", "placement", source_key)):
                return False
            if key == "hyperlinks" and (not isinstance(item.get("text"), str) or not item["text"].strip()):
                return False
            if key in {"embeds", "hyperlinks"}:
                try:
                    url = item["url"]
                    parsed = urlsplit(url)
                    if (parsed.scheme not in ("http", "https") or not parsed.hostname
                            or parsed.username is not None or parsed.password is not None
                            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url)):
                        return False
                    parsed.port
                except ValueError:
                    return False
    cards = layout["footer_cards"]
    urls = cards.get("urls")
    if not isinstance(urls, list) or any(not isinstance(url, str) for url in urls):
        return False
    if cards["decision"] == "omit":
        return urls == []
    if not urls or len(urls) != len(set(urls)):
        return False
    try:
        return all(urlsplit(url).scheme in ("http", "https") and bool(urlsplit(url).netloc)
                   and not any(c.isspace() for c in url) for url in urls)
    except ValueError:
        return False


def history_application_target(packet: dict, stage: str, base_dir: Path, draft_dir: Path) -> Path:
    """局所編集JSONを全文と誤認せず、レビューする実本文を明示させる。"""
    value = packet.get("proposed_draft") if stage == "edit" else packet.get("draft")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("history適用対象が必要です")
    target = Path(value)
    target = target if target.is_absolute() else base_dir / target
    if not target.resolve().is_relative_to(draft_dir):
        raise ValueError("history適用対象がdrafts保存先の外です")
    try:
        parsed = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        parsed = None
    if target.suffix == ".json" or isinstance(parsed, (dict, list)):
        plan = packet.get("edit_plan")
        value = plan.get("history_application_target") if isinstance(plan, dict) and stage == "edit" else None
        if not isinstance(value, str) or not value.strip():
            raise ValueError("JSON局所planにはhistory_application_targetの全文pathが必要です")
        target = Path(value)
        target = target if target.is_absolute() else base_dir / target
        if not target.resolve().is_relative_to(draft_dir):
            raise ValueError("history適用対象がdrafts保存先の外です")
        try:
            parsed = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            parsed = None
        if target.suffix == ".json" or isinstance(parsed, (dict, list)):
            raise ValueError("history適用対象を局所planで代用できません")
    return target


def check_packet(packet: Any, stage: str, conversation_id: str, base_dir: Path = Path("."), *, settings_path: Path | None = None) -> dict:
    """ファイルを変更せず、現在会話と現在の内容に対する承認を照合する。"""
    reasons: list[str] = []
    subjects: dict[str, str] = {}
    hashes: dict[str, str] = {}
    result = {"status": "blocked", "reasons": reasons, "subject_hashes": subjects,
              "content_hashes": hashes, "manual_publish_required": stage == "publish",
              "automation_allowed": False, "authenticity_notice": AUTHENTICITY}
    if not isinstance(packet, dict) or stage not in STAGES:
        reasons.append("packetまたはstageが不正です")
        return result
    if packet.get("schema_version") != SCHEMA:
        reasons.append("schema_versionが不正です")
    for name in ("article_id", "conversation_id"):
        if not isinstance(packet.get(name), str) or not packet[name].strip():
            reasons.append(f"{name}が必要です")
    if not isinstance(conversation_id, str) or not conversation_id.strip() or packet.get("conversation_id") != conversation_id:
        reasons.append("現在のconversation_idと一致しません")
    if packet.get("route") not in tuple(ROUTES):
        reasons.append("routeが不正です")
    storage_dirs: dict[str, Path] = {}
    expected = {}
    quality_policy = None
    history_policy = None
    history_application_refs = None
    publication_drafts_policy = None
    try:
        expected, storage_dirs = read_workspace_settings(settings_path, packet.get("article_id"))
        quality_policy = expected.get("research_quality_policy")
        history_policy = expected.get("history_learning_policy")
        publication_drafts_policy = expected.get("publication_drafts_policy")
        result["expected_readback"] = expected
        hashes["workspace_settings"] = expected["settings_sha256"]
        hashes["style_references"] = canonical_sha256(expected["reference_hashes"])
        if packet.get("ssot_readback") != expected:
            reasons.append("ssot_readbackが現在の外部設定・文体参照と一致しません")
    except (OSError, ValueError, TypeError, RuntimeError, RecursionError):
        reasons.append("外部settingsまたは文体参照を検証できません")
    if "settings_path" in packet or "nps_settings" in packet or "workspace_settings" in packet:
        reasons.append("packetから外部settingsを指定または上書きできません")
    update_permission: dict = {}
    receipts = packet.get("receipts")
    if not isinstance(receipts, list) or any(not isinstance(r, dict) for r in receipts):
        reasons.append("receiptsはオブジェクトの配列である必要があります")
        receipts = []

    file_bytes: dict[str, bytes] = {}

    def file_hash(name: str, nonempty: bool = False) -> None:
        value = packet.get(name)
        if not isinstance(value, str) or not value.strip():
            reasons.append(f"{name}のパスが必要です")
            return
        path = Path(value)
        if not path.is_absolute():
            path = base_dir / path
        try:
            storage_key = "sources" if name == "source_snapshot" else "drafts" if name in {"draft", "proposed_draft"} else None
            if storage_key in storage_dirs and not path.resolve().is_relative_to(storage_dirs[storage_key]):
                reasons.append(f"{name}が指定保存先の外にあります")
                return
            data = path.read_bytes()
            if nonempty and not data.strip():
                raise ValueError("empty")
            hashes[name] = hashlib.sha256(data).hexdigest()
            file_bytes[name] = data
        except (OSError, ValueError):
            reasons.append(f"{name}が存在しないか読取不能または空です")

    file_hash("source_snapshot", nonempty=True)
    file_hash("draft", nonempty=True)
    try:
        read_article_feedback = _load_sibling_module("note_feedback").read_article_feedback
        source_path = Path(packet["source_snapshot"])
        draft_path = Path(packet["draft"])
        feedback = read_article_feedback(
            storage_dirs, packet["article_id"],
            source_path if source_path.is_absolute() else base_dir / source_path,
            draft_path if draft_path.is_absolute() else base_dir / draft_path)
        result["expected_feedback_readback"] = feedback
        hashes["feedback"] = canonical_sha256(feedback)
        if packet.get("feedback_readback") != feedback:
            reasons.append("feedback_readbackが現在の記事別履歴と一致しません")
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, RuntimeError, RecursionError):
        reasons.append("記事別feedbackが欠落・不正または現在の原稿と不一致です")
    if "prepublish_review_receipt" in packet:
        file_hash("prepublish_review_receipt", nonempty=True)
        try:
            validate_pre_publish_review_receipt = _load_sibling_module("pre_publish_check").validate_pre_publish_review_receipt
            load_editorial_review_receipt = _load_sibling_module("pre_publish_check").load_editorial_review_receipt
            receipt_path = Path(packet["prepublish_review_receipt"])
            if not receipt_path.is_absolute():
                receipt_path = base_dir / receipt_path
            draft_path = Path(packet["draft"])
            if not draft_path.is_absolute():
                draft_path = base_dir / draft_path
            errors = validate_pre_publish_review_receipt(
                load_editorial_review_receipt(receipt_path), draft_path.read_text(encoding="utf-8"),
                article_id=packet["article_id"], conversation_id=conversation_id)
            if errors:
                reasons.append("本人構成のレビュー記録が現稿と不一致または不正です: " + "; ".join(errors))
            else:
                result["editorial_review"] = "review_required"
        except (OSError, ValueError, TypeError, KeyError, UnicodeError):
            reasons.append("本人構成のレビュー記録を検証できません")
    edit_plan = packet.get("edit_plan")
    layout_edit = stage == "edit" and isinstance(edit_plan, dict) and (edit_plan.get("toc") is True or bool(edit_plan.get("urls")) or bool(edit_plan.get("footer_embed_urls")) or bool(edit_plan.get("footer_cards")) or bool(edit_plan.get("illustrations")) or bool(edit_plan.get("embeds")) or "hyperlinks" in edit_plan)
    layout_needed = stage in {"layout", "settings", "publish"} or layout_edit
    if layout_needed:
        if validate_layout(packet.get("layout")):
            hashes["layout"] = canonical_sha256(packet["layout"])
            if layout_edit:
                if edit_plan.get("toc") is True and packet["layout"]["toc"]["decision"] != "include":
                    reasons.append("目次追加操作が採用済みlayoutと一致しません")
                for kind in ("illustrations", "embeds", "hyperlinks"):
                    planned_items = edit_plan.get(kind)
                    choice = packet["layout"][kind]
                    specified = kind in edit_plan if kind == "hyperlinks" else bool(planned_items)
                    if specified and (not isinstance(planned_items, list) or planned_items != choice["items"]):
                        label = {"illustrations": "挿絵", "embeds": "埋め込み", "hyperlinks": "ハイパーリンク"}[kind]
                        reasons.append(f"{label}追加操作が採用済みlayoutと一致しません")
                planned_urls = edit_plan.get("urls", edit_plan.get("footer_embed_urls", edit_plan.get("footer_cards", [])))
                if planned_urls and (not isinstance(planned_urls, list) or planned_urls != packet["layout"]["footer_cards"]["urls"]):
                    reasons.append("末尾カード追加URLが採用済みlayoutと一致しません")
        else:
            reasons.append("layoutにはタイトル画・目次・末尾カード・挿絵・埋め込みの明示的な採否、理由、採用内容と提案・対話・決定の参照が必要です")
    if stage == "edit" or layout_needed:
        settings = packet.get("settings")
        account = settings.get("account") if isinstance(settings, dict) else None
        if not isinstance(account, str) or not account.strip():
            reasons.append("編集にはsettings.accountが必要です")
        else:
            hashes["account"] = canonical_sha256(account)
    if stage == "edit":
        file_hash("proposed_draft", nonempty=True)
        if not isinstance(packet.get("edit_plan"), dict):
            reasons.append("edit_planが必要です")
        else:
            try:
                hashes["edit_plan"] = canonical_sha256(packet["edit_plan"])
            except (TypeError, ValueError):
                reasons.append("edit_planが不正です")
    target_key = "proposed_draft" if stage == "edit" else "draft"
    if target_key in file_bytes:
        try:
            linebreak = _load_sibling_module("note_linebreak_gate").validate_draft(
                file_bytes[target_key].decode("utf-8-sig"), expected.get("linebreak_policy") if storage_dirs else None)
            result["linebreak_check"] = linebreak
            reasons.extend("linebreak: " + item["code"] for item in linebreak["issues"])
        except UnicodeError:
            reasons.append("linebreak: draft must be valid UTF-8")
    fidelity_policy = expected.get("conversation_fidelity_policy") if storage_dirs else None
    if fidelity_policy and fidelity_policy.get("required") and target_key in file_bytes:
        fidelity_target = Path(packet[target_key])
        if not fidelity_target.is_absolute():
            fidelity_target = base_dir / fidelity_target
        fidelity = _load_sibling_module("provenance_label_check").check_conversation_fidelity(
            fidelity_target, fidelity_policy, packet["article_id"], conversation_id)
        result["conversation_fidelity"] = fidelity
        reasons.extend("conversation_fidelity: " + error for error in fidelity["errors"])
        if fidelity.get("hashes", {}).get("draft") not in (None, hashes.get(target_key)):
            reasons.append("conversation_fidelity: 検査対象が編集対象の版と不一致")
        if fidelity["status"] == "mechanical_ok":
            hashes["conversation_fidelity"] = canonical_sha256(fidelity.get("approval_hashes", fidelity["hashes"]))
    for name in ("draft", "proposed_draft") if stage == "edit" else ("draft",):
        if "source_snapshot" in hashes and name in hashes:
            source_path = Path(packet["source_snapshot"])
            target_path = Path(packet[name])
            if not source_path.is_absolute():
                source_path = base_dir / source_path
            if not target_path.is_absolute():
                target_path = base_dir / target_path
            try:
                if source_path.resolve() == target_path.resolve() or source_path.samefile(target_path):
                    reasons.append(f"source_snapshotと{name}は別ファイルである必要があります")
            except OSError:
                reasons.append("原資料と原稿の独立性を確認できません")
    if history_policy and history_policy["required"]:
        try:
            read_feedback_record = _load_sibling_module("note_feedback").read_feedback_record
            check_history_learning_from_settings = _load_sibling_module("note_authorship_gate").check_history_learning_from_settings
            record, readback = read_feedback_record(storage_dirs, packet["article_id"])
            if readback != result.get("expected_feedback_readback"):
                raise ValueError("history適用のfeedbackが変更されています")
            target = history_application_target(packet, stage, base_dir, storage_dirs["drafts"])
            evidence_value = packet.get("history_evidence")
            if evidence_value is None:
                evidence_path = target.with_suffix(".authorship.json")
            elif isinstance(evidence_value, str) and evidence_value.strip():
                evidence_path = Path(evidence_value)
                evidence_path = evidence_path if evidence_path.is_absolute() else base_dir / evidence_path
            else:
                raise ValueError("history evidence pathが不正です")
            baseline = Path(packet['draft'])
            baseline = baseline if baseline.is_absolute() else base_dir / baseline
            checked = check_history_learning_from_settings(target, settings_path, packet["article_id"], evidence_path,
                **({'current_draft': baseline} if stage == 'edit' else {}))
            if stage == 'edit' and checked.get('hashes', {}).get('current_draft') != hashes.get('draft'):
                raise ValueError("history適用の現在本文がpacket検査時から変更されています")
            if stage == 'edit':
                proposal = Path(packet['proposed_draft'])
                proposal = proposal if proposal.is_absolute() else base_dir / proposal
                if (target.resolve() == proposal.resolve()
                        and checked.get('hashes', {}).get('target') != hashes.get('proposed_draft')):
                    raise ValueError("history適用の提案本文がpacket検査時から変更されています")
            if checked.get("settings_readback") != expected or checked.get("feedback_readback") != readback:
                raise ValueError("history適用の設定またはfeedbackが変更されています")
            result["history_learning"] = checked
            reasons.extend("history_learning: " + error for error in checked["errors"])
            if checked["status"] == "mechanical_ok":
                # editで同じ本文を確認する時の重複キーを承認対象へ混ぜない。
                # 本文が異なる場合はcurrent_draftを保持し、提案との違いを束縛する。
                application_hashes = dict(checked["hashes"])
                if application_hashes.get("current_draft") == application_hashes.get("target"):
                    application_hashes.pop("current_draft", None)
                hashes["history_application"] = canonical_sha256(application_hashes)
                history_application_refs = {entry["evidence_ref"] for entry in record["entries"]
                                            if "history_source_id" in entry
                                            and entry.get("application_status") in {"applied", "preserved"}}
        except (OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            reasons.append("history_learningの回収と現在本文への適用を検証できません")

    if stage in {"research", "publish"}:
        file_hash("research_report", nonempty=True)
        if quality_policy and quality_policy["required"]:
            try:
                check_quality_report = _load_sibling_module("note_research_quality").check_quality_report
                article_directory = _load_sibling_module("note_feedback").article_directory
                confined = _load_sibling_module("note_feedback").confined
                feedback_path = confined(article_directory(storage_dirs, packet["article_id"]), "feedback.json")
                feedback_bytes = feedback_path.read_bytes()
                if hashlib.sha256(feedback_bytes).hexdigest() != result.get("expected_feedback_readback", {}).get("record_sha256"):
                    raise ValueError("検査中にfeedbackが変更されました")
                feedback_record = parse_packet(feedback_bytes)
                refs = {entry["evidence_ref"] for entry in feedback_record["entries"]}
                report_path = Path(packet["research_report"])
                report_dir = (report_path if report_path.is_absolute() else base_dir / report_path).parent
                evidence = check_quality_report(file_bytes["research_report"], quality_policy,
                    article_id=packet["article_id"], base_dir=report_dir, feedback_refs=refs,
                    history_application_refs=history_application_refs)
                hashes["research_quality_evidence"] = canonical_sha256(evidence)
            except (OSError, ValueError, TypeError, KeyError, UnicodeError, RuntimeError, RecursionError) as exc:
                reasons.append(f"調査品質の検証に失敗しました: {exc}")
    if stage in {"settings", "publish"}:
        settings = packet.get("settings")
        required = {"account", "tags", "magazine", "visibility", "article_type", "price", "sns_share", "publish_mode", "schedule_at", "image_rights_confirmed", "cover_image"}
        valid = isinstance(settings, dict) and required <= settings.keys()
        if valid:
            valid = (all(isinstance(settings[k], str) and bool(settings[k].strip()) for k in ("account", "visibility"))
                     and settings["visibility"] == "public"
                     and isinstance(settings["tags"], list) and all(isinstance(t, str) and bool(t.strip()) for t in settings["tags"])
                     and all(settings[k] is None or isinstance(settings[k], str) and bool(settings[k].strip()) for k in ("magazine", "cover_image"))
                     and type(settings["sns_share"]) is bool and settings["image_rights_confirmed"] is True
                     and type(settings["price"]) in (int, float)
                     and ((settings["article_type"] == "free" and settings["price"] == 0)
                          or (settings["article_type"] == "paid" and settings["price"] > 0))
                     and settings["publish_mode"] in ("immediate", "scheduled"))
            if settings["publish_mode"] == "immediate":
                valid = valid and settings["schedule_at"] is None
            elif settings["publish_mode"] == "scheduled":
                try:
                    timestamp = datetime.fromisoformat(settings["schedule_at"])
                    valid = valid and timestamp.utcoffset() is not None
                except (ValueError, TypeError):
                    valid = False
        if not valid:
            reasons.append("settingsが不足または不正です（画像権利確認と明示的な全設定が必要です）")
        else:
            try:
                hashes["settings"] = canonical_sha256(settings)
                if validate_layout(packet.get("layout")):
                    expected_cover = "include" if settings["cover_image"] is not None else "omit"
                    if packet["layout"]["cover"]["decision"] != expected_cover:
                        reasons.append("タイトル画の設定が採用済みlayoutと一致しません")
                if settings["cover_image"] is not None:
                    cover_path = Path(settings["cover_image"])
                    if not cover_path.is_absolute():
                        cover_path = base_dir / cover_path
                    try:
                        cover_bytes = cover_path.read_bytes()
                        if not cover_bytes:
                            raise ValueError("empty cover")
                        hashes["cover_image"] = hashlib.sha256(cover_bytes).hexdigest()
                    except (OSError, ValueError):
                        reasons.append("cover_imageが存在しないか読取不能または空です")
            except (TypeError, ValueError):
                reasons.append("settingsを正規化できません")

    if stage in {"settings", "publish"}:
        normalize_tag = _load_sibling_module("note_editor_prepublish_verify").normalize_tag
        tag_operation_preflight = _load_sibling_module("note_editor_prepublish_verify").tag_operation_preflight
        validate_tag_design = _load_sibling_module("note_editor_prepublish_verify").validate_tag_design
        settings_value = packet.get("settings") if isinstance(packet.get("settings"), dict) else {}
        design = packet.get("tag_design")
        try:
            draft_text = file_bytes.get("draft", b"").decode("utf-8")
            tag_errors = validate_tag_design(design, packet.get("article_id"), settings_value.get("tags"),
                                            draft_text, article_lane=packet.get("article_lane", "production_candidate"),
                                            reference_policy=expected.get("tag_reference_policy") if storage_dirs else None,
                                            reference_hashes=expected.get("reference_hashes") if storage_dirs else None,
                                            count_policy=expected.get("tag_count_policy") if storage_dirs else None)
            reasons.extend("tag_design: " + error for error in tag_errors)
            if isinstance(design, dict):
                hashes["tag_design"] = canonical_sha256(design)
            if stage == "publish" or "tag_preflight" in packet:
                selected = tag_operation_preflight(packet.get("tag_preflight"), packet.get("article_id"),
                                                   settings_value.get("account"), expected_tags=settings_value.get("tags"))
                reasons.extend("tag_selection: " + error for error in selected["reasons"])
                if stage == "publish" and not selected["reasons"]:
                    current_tags = packet["tag_preflight"]["current"]["selected_tags"]
                    tags = settings_value.get("tags")
                    if (not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags)
                            or set(map(normalize_tag, current_tags)) != set(map(normalize_tag, tags))):
                        reasons.append("tag_selection: tag_selected_design_mismatch")
                    hashes["tag_selection"] = canonical_sha256(packet["tag_preflight"])
        except (UnicodeError, TypeError, ValueError):
            reasons.append("tag_designを正規化または本文と照合できません")

    if stage == "publish":
        footer_policy = expected.get("footer_readback_policy")
        readback = _load_sibling_module("note_footer_selection").check_readback(
            footer_policy, packet.get("footer_readback"), article_id=packet["article_id"],
            article_sha256=hashes.get("draft"), layout=packet.get("layout"),
            expected_url=packet.get("edit_plan", {}).get("target_url"))
        result["footer_readback"] = readback
        if readback["status"] == "blocked":
            reasons.extend(readback["errors"])
        elif readback["status"] == "ok":
            hashes["footer_readback"] = canonical_sha256(readback["hashes"])
        check_drafts = _load_sibling_module("note_publication_drafts").check_manifest
        draft_value = packet.get("draft")
        publication_drafts = check_drafts(publication_drafts_policy,
            packet.get("publication_drafts_manifest"), article_id=packet["article_id"],
            draft_path=Path(draft_value) if isinstance(draft_value, str) else Path(""),
            storage_dirs=storage_dirs, base_dir=base_dir,
            expected_article_sha256=hashes.get("draft"))
        result["publication_drafts"] = publication_drafts
        if publication_drafts["status"] == "blocked":
            reasons.extend(publication_drafts["errors"])
        elif publication_drafts["status"] == "ok":
            hashes["publication_drafts"] = canonical_sha256(publication_drafts["hashes"])

    check_image_settings = _load_sibling_module("image_reference_gate").check_settings
    cover_value = packet.get("settings", {}).get("cover_image") if isinstance(packet.get("settings"), dict) else None
    cover_path = Path(cover_value) if isinstance(cover_value, str) and cover_value.strip() else None
    if cover_path is not None and not cover_path.is_absolute():
        cover_path = base_dir / cover_path
    image_stage = "publish" if stage == "publish" else "image_edit" if cover_path is not None else "qa"
    image_result = (check_image_settings(settings_path, stage=image_stage, output_path=cover_path, article_id=packet.get("article_id"))
                    if stage in {"edit", "settings", "publish"}
                    else {"status": "not_required", "hashes": {}, "errors": []})
    if image_result["status"] == "blocked":
        reasons.extend("image_reference: " + error for error in image_result["errors"])
    elif image_result["status"] == "ok":
        hashes["image_reference_evidence"] = canonical_sha256(image_result["hashes"])

    if stage == "publish":
        update_permission = _load_sibling_module("note_update_authorization").authorize_update(
            settings_path, packet.get("update_observation"))
        if update_permission.get("automation_allowed"):
            update = packet["update_observation"]
            settings_value = packet.get("settings") if isinstance(packet.get("settings"), dict) else {}
            plan_value = packet.get("edit_plan") if isinstance(packet.get("edit_plan"), dict) else {}
            denial = None
            if (settings_value.get("account") != update.get("account")
                    or plan_value.get("target_url") !=
                    f'https://editor.note.com/notes/{update.get("note_id")}/edit/'):
                denial = "update_target_mismatch"
            elif (settings_value.get("publish_mode") != "immediate"
                    or settings_value.get("schedule_at") is not None
                    or settings_value.get("sns_share") is not False):
                denial = "update_operation_outside_scope"
            elif hashes.get("draft") is None or any(
                    update.get(key) != hashes["draft"] for key in
                    ("approved_content_sha256", "editor_content_sha256", "saved_content_sha256")):
                # publishはdraftの実bytesを対象にする。観測内の値が互いに等しいだけでは足りない。
                denial = "update_current_content_mismatch"
            elif hashes.get("settings") is None or update.get("current_settings_sha256") != hashes["settings"]:
                denial = "update_current_settings_mismatch"
            if denial:
                update_permission = {"automation_allowed": False, "manual_publish_required": True,
                                     "reason": denial}
        if "update_observation" in packet:
            result["update_authorization"] = update_permission
            if not update_permission.get("automation_allowed"):
                reasons.append("既存記事更新の利用者許可または現稿照合が不足しています")

    combinations = {"edit": ("source_snapshot", "draft", "proposed_draft", "edit_plan", "account"),
                    "layout": ("source_snapshot", "draft", "layout", "account"),
                    "research": ("source_snapshot", "draft", "research_report"), "settings": ("source_snapshot", "draft", "settings"),
                    "publish": ("source_snapshot", "draft", "research_report", "settings")}
    needed = ("research", "layout", "settings", "publish") if stage == "publish" else ("layout", stage) if stage == "settings" or layout_edit else (stage,)
    for item in needed:
        keys = combinations[item] + ("workspace_settings", "style_references", "feedback")
        if history_policy and history_policy["required"]:
            keys += ("history_application",)
        if fidelity_policy and fidelity_policy.get("required"):
            keys += ("conversation_fidelity",)
        if item in {"settings", "publish"}:
            keys += ("tag_design",)
        if item == "publish":
            keys += ("tag_selection",)
            if publication_drafts_policy and publication_drafts_policy["required"]:
                keys += ("publication_drafts",)
            if expected and expected.get("footer_readback_policy", {}).get("required"):
                keys += ("footer_readback",)
        if image_result["status"] == "ok" and item in {"edit", "settings", "publish"}:
            keys += ("image_reference_evidence",)
        if "prepublish_review_receipt" in packet:
            keys += ("prepublish_review_receipt",)
        if item in {"research", "publish"} and quality_policy and quality_policy["required"]:
            keys += ("research_quality_evidence",)
        if item in {"settings", "publish"} and isinstance(packet.get("settings"), dict) and packet["settings"].get("cover_image") is not None:
            keys = keys + ("cover_image",)
        if not all(key in hashes for key in keys):
            continue
        subject = canonical_sha256({key: hashes[key] for key in keys})
        subjects[item] = subject
        # 任意policyは現在会話の本人による更新依頼を代替しない。
        # その依頼を同じ公開対象へ束縛できた場合だけ、追加の最終質問を省略する。
        if item == "publish" and update_permission.get("automation_allowed"):
            requests = [r for r in receipts if r.get("stage") == "update_request"]
            update = packet["update_observation"]
            if (not requests or not all(
                    not receipt_mismatches(r, packet, conversation_id, subject)
                    and r.get("operation") == "update_existing"
                    and r.get("note_id") == update.get("note_id")
                    and r.get("evidence_ref") == update.get("edit_request_ref")
                    for r in requests)):
                reasons.append("既存記事更新の現在会話に束縛した本人依頼が必要です")
            continue
        matches = [r for r in receipts if r.get("stage") == item]
        if not matches or not all(not receipt_mismatches(r, packet, conversation_id, subject) for r in matches):
            reasons.append(f"{item}の現在内容に一致する人間承認が必要です")
    if not reasons:
        result["status"] = "approved"
        if stage == "publish" and update_permission.get("automation_allowed"):
            result["automation_allowed"] = True
            result["manual_publish_required"] = False
    return result



def receipt_mismatches(receipt: dict, packet: dict, conversation_id: str, subject: str) -> list[str]:
    """従来のreceipt照合条件をそのまま診断にも使う。承認を発行しない。"""
    mismatches = []
    for key, expected, label in (
        ("article_id", packet.get("article_id"), "別記事"),
        ("conversation_id", conversation_id, "別会話"),
        ("subject_sha256", subject, "承認対象の版が変更"),
        ("actor", "user", "本人以外"), ("status", "approved", "未承認"),
    ):
        if receipt.get(key) != expected:
            mismatches.append(label)
    try:
        observed = datetime.fromisoformat(receipt.get("observed_at"))
        if observed.utcoffset() is None:
            mismatches.append("承認日時にtimezoneがない")
    except (ValueError, TypeError):
        mismatches.append("承認日時が不正")
    if not isinstance(receipt.get("evidence_ref"), str) or not receipt["evidence_ref"].strip():
        mismatches.append("本人回答の証拠参照がない")
    return mismatches


def list_gates(packet: Any, conversation_id: str, base_dir: Path = Path("."), *, settings_path: Path | None = None) -> dict:
    """現在packetの一覧。承認状態と依存を含む実行可否を分け、公開事実を推定しない。"""
    rows = []
    for stage in ("edit", "research", "layout", "settings", "publish"):
        checked = check_packet(packet, stage, conversation_id, base_dir, settings_path=settings_path)
        subject = checked["subject_hashes"].get(stage)
        receipts = packet.get("receipts", []) if isinstance(packet, dict) else []
        matches = [r for r in receipts if isinstance(r, dict) and r.get("stage") == stage] if isinstance(receipts, list) else []
        invalidation = sorted({reason for r in matches for reason in
                               receipt_mismatches(r, packet, conversation_id, subject)}) if subject else []
        approval = "unavailable" if subject is None else "pending" if not matches else "invalidated" if invalidation else "approved"
        if approval == "approved":
            action = "現在版の再確認質問は不要。依存・検査の停止理由を解消" if checked["status"] != "approved" else "人間の最終操作へ渡す" if stage == "publish" else "承認済み対象の次工程へ進む"
        elif approval == "invalidated":
            action = "失効理由と現在値への変更を提示し、対象を再確認"
        elif approval == "pending":
            action = "具体的な対象・現在値・提案値を確認カードで提示"
        else:
            action = "欠落・不正な資料と読戻しを修復して再検査"
        rows.append(dict(stage=stage, article_id=packet.get("article_id") if isinstance(packet, dict) else None,
                         conversation_id=conversation_id, subject_sha256=subject,
                         approval_status=approval, status=checked["status"],
                         evidence_refs=[r.get("evidence_ref") for r in matches if isinstance(r.get("evidence_ref"), str)],
                         invalidation_reasons=invalidation, reasons=checked["reasons"], next_action=action))
    if isinstance(packet, dict):
        layout_row = next(row for row in rows if row["stage"] == "layout")
        layout = packet.get("layout")
        layout_row["layout_review"] = ({key: layout.get(key) for key in
            ("cover", "toc", "footer_cards", "illustrations", "embeds", "hyperlinks", "review")}
            if isinstance(layout, dict) else None)
        # 5段階は増やさず、各段階で確認する具体的な対象を常に表示する。
        # 未言及や欠落を「不要」「承認済み」に読み替えない。
        layout = layout if isinstance(layout, dict) else {}
        layout_row["review_items"] = [
            dict(key=key, decision=value.get("decision"), reason=value.get("reason"),
                 status="missing" if not value else layout_row["approval_status"],
                 proposal=value,
                 next_action="候補・配置・採否を具体的に提示" if not value else layout_row["next_action"])
            for key in ("cover", "toc", "footer_cards", "illustrations", "embeds", "hyperlinks")
            for value in [layout.get(key) if isinstance(layout.get(key), dict) else {}]
        ]
        settings_row = next(row for row in rows if row["stage"] == "settings")
        design = packet.get("tag_design")
        settings_row["tag_review"] = dict(
            status="missing" if not isinstance(design, dict) else settings_row["approval_status"],
            design=design, selection=packet.get("tag_preflight"),
            next_action="内容・発見・ブランドの比較根拠と候補の採否を確認し、実選択を別途読戻す",
        )
    return dict(status="approved" if all(row["status"] == "approved" for row in rows) else "blocked",
                gates=rows, automation_allowed=False, manual_publish_required=True,
                authenticity_notice=AUTHENTICITY)


def load_and_list(packet_path: Path | str, conversation_id: str, *, settings_path: Path | None = None) -> dict:
    path = Path(packet_path)
    try:
        return list_gates(load_packet(path), conversation_id, path.resolve().parent, settings_path=settings_path)
    except (OSError, ValueError, UnicodeError, RecursionError):
        result = list_gates(None, conversation_id, settings_path=settings_path)
        for row in result["gates"]:
            row["reasons"] = ["packet JSONが存在しないか不正です"]
        return result

def parse_packet(raw: bytes | str) -> Any:
    """重複キー、非有限数値を拒否してJSONを解析する。"""
    def reject_constant(value: str) -> None:
        raise ValueError(value)

    def unique_object(pairs: list[tuple[str, Any]]) -> dict:
        value: dict = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value

    return json.loads(raw, parse_constant=reject_constant,
                      object_pairs_hook=unique_object)


def load_packet(packet_path: Path | str) -> Any:
    """JSONを一度読む。重複キー、非有限数値、読取異常は例外にする。"""
    return parse_packet(Path(packet_path).read_bytes())


def load_and_check(packet_path: Path | str, stage: str, conversation_id: str, *, settings_path: Path | None = None) -> dict:
    """packetの親を相対パス基準として読取り、JSON異常もblockedにする。"""
    path = Path(packet_path)
    try:
        packet = load_packet(path)
        return check_packet(packet, stage, conversation_id, path.resolve().parent, settings_path=settings_path)
    except (OSError, ValueError, UnicodeError, RecursionError):
        result = check_packet(None, stage, conversation_id)
        result["reasons"] = ["packet JSONが存在しないか不正です"]
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--stage", choices=sorted(STAGES))
    mode.add_argument("--list-gates", action="store_true", help="各ゲートの現在版・承認状態・根拠・次の操作を読取り専用で一覧化")
    parser.add_argument("--conversation-id", required=True)
    parser.add_argument("--settings", required=True, type=Path)
    args = parser.parse_args()
    result = load_and_list(args.packet, args.conversation_id, settings_path=args.settings) if args.list_gates else load_and_check(args.packet, args.stage, args.conversation_id, settings_path=args.settings)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["status"] == "approved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
