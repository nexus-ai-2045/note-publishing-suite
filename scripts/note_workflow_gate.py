#!/usr/bin/env python3
"""読取り専用の承認照合。receipt の発行と真正性の担保は trusted runtime の責務。"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCHEMA = "note-workflow-review/v1"
ROUTES = {"direct_draft", "source_article", "collaborative"}
STAGES = {"edit", "research", "layout", "settings", "publish"}
AUTHENTICITY = "ローカルJSONは承認の真正性を暗号学的に証明しません。trusted runtime が人間の承認receiptを管理します。"


def canonical_sha256(value: Any) -> str:
    """UTF-8、キー順、空白なしのJSONをハッシュする。"""
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def read_workspace_settings(settings_path: Path | None, article_id: str) -> tuple[dict, dict[str, Path]]:
    """利用のたびに外部設定と文体参照を読み直す。書込みや既定設定作成はしない。"""
    if settings_path is None:
        raise ValueError("外部settingsの指定が必要です")
    config_path = Path(settings_path).resolve()
    if config_path.is_relative_to(PACKAGE_ROOT):
        raise ValueError("settingsはNPS package外に置く必要があります")
    raw = config_path.read_bytes()
    config = parse_packet(raw)
    if not isinstance(config, dict) or config.get("schema_version") != "nps-workspace-settings/v1":
        raise ValueError("外部settingsのschema_versionが不正です")

    def resolve_path(value: Any, base: Path) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("設定パスが不足または不正です")
        candidate = Path(value)
        path = (candidate if candidate.is_absolute() else base / candidate).resolve()
        if path.is_relative_to(PACKAGE_ROOT):
            raise ValueError("設定・保存先・文体参照はNPS package外に置く必要があります")
        return path

    workspace = resolve_path(config.get("workspace_root"), config_path.parent)
    storage = config.get("storage")
    style = config.get("style")
    if not isinstance(storage, dict) or not isinstance(style, dict):
        raise ValueError("storageとstyleが必要です")
    dirs = {key: resolve_path(storage.get(key), workspace) for key in ("drafts", "sources", "feedback")}
    default = resolve_path(style.get("default_profile"), workspace)
    profiles = style.get("article_profiles")
    if not isinstance(profiles, dict) or any(not isinstance(k, str) or not isinstance(v, list) or any(not isinstance(p, str) or not p.strip() for p in v) for k, v in profiles.items()):
        raise ValueError("article_profilesが不正です")
    refs = [default] + [resolve_path(value, workspace) for value in profiles.get(article_id, [])]
    reference_hashes = {}
    for path in refs:
        data = path.read_bytes()
        if not data.strip():
            raise ValueError("文体参照が空です")
        reference_hashes[str(path)] = hashlib.sha256(data).hexdigest()
    return {"settings_sha256": hashlib.sha256(raw).hexdigest(), "reference_hashes": reference_hashes}, dirs


def validate_layout(layout: Any) -> bool:
    """目次と末尾カードの採否は省略せず、採用URLも承認対象にする。"""
    if not isinstance(layout, dict):
        return False
    for key in ("toc", "footer_cards"):
        item = layout.get(key)
        if not isinstance(item, dict) or item.get("decision") not in ("include", "omit"):
            return False
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
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
    try:
        expected, storage_dirs = read_workspace_settings(settings_path, packet.get("article_id"))
        result["expected_readback"] = expected
        hashes["workspace_settings"] = expected["settings_sha256"]
        hashes["style_references"] = canonical_sha256(expected["reference_hashes"])
        if packet.get("ssot_readback") != expected:
            reasons.append("ssot_readbackが現在の外部設定・文体参照と一致しません")
    except (OSError, ValueError, TypeError, RuntimeError, RecursionError):
        reasons.append("外部settingsまたは文体参照を検証できません")
    if "settings_path" in packet or "nps_settings" in packet or "workspace_settings" in packet:
        reasons.append("packetから外部settingsを指定または上書きできません")
    receipts = packet.get("receipts")
    if not isinstance(receipts, list) or any(not isinstance(r, dict) for r in receipts):
        reasons.append("receiptsはオブジェクトの配列である必要があります")
        receipts = []

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
        except (OSError, ValueError):
            reasons.append(f"{name}が存在しないか読取不能または空です")

    file_hash("source_snapshot", nonempty=True)
    file_hash("draft", nonempty=True)
    try:
        from note_feedback import read_article_feedback
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
    edit_plan = packet.get("edit_plan")
    layout_edit = stage == "edit" and isinstance(edit_plan, dict) and (edit_plan.get("toc") is True or bool(edit_plan.get("urls")) or bool(edit_plan.get("footer_embed_urls")) or bool(edit_plan.get("footer_cards")))
    layout_needed = stage in {"layout", "settings", "publish"} or layout_edit
    if layout_needed:
        if validate_layout(packet.get("layout")):
            hashes["layout"] = canonical_sha256(packet["layout"])
            if layout_edit:
                if edit_plan.get("toc") is True and packet["layout"]["toc"]["decision"] != "include":
                    reasons.append("目次追加操作が採用済みlayoutと一致しません")
                planned_urls = edit_plan.get("urls", edit_plan.get("footer_embed_urls", edit_plan.get("footer_cards", [])))
                if planned_urls and (not isinstance(planned_urls, list) or planned_urls != packet["layout"]["footer_cards"]["urls"]):
                    reasons.append("末尾カード追加URLが採用済みlayoutと一致しません")
        else:
            reasons.append("layoutには目次・末尾カードの明示的な採否、理由、採用URLが必要です")
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
    if stage in {"research", "publish"}:
        file_hash("research_report", nonempty=True)
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

    combinations = {"edit": ("source_snapshot", "draft", "proposed_draft", "edit_plan", "account"),
                    "layout": ("source_snapshot", "draft", "layout", "account"),
                    "research": ("source_snapshot", "draft", "research_report"), "settings": ("source_snapshot", "draft", "settings"),
                    "publish": ("source_snapshot", "draft", "research_report", "settings")}
    needed = ("research", "layout", "settings", "publish") if stage == "publish" else ("layout", stage) if stage == "settings" or layout_edit else (stage,)
    for item in needed:
        keys = combinations[item] + ("workspace_settings", "style_references", "feedback")
        if item in {"settings", "publish"} and isinstance(packet.get("settings"), dict) and packet["settings"].get("cover_image") is not None:
            keys = keys + ("cover_image",)
        if not all(key in hashes for key in keys):
            continue
        subject = canonical_sha256({key: hashes[key] for key in keys})
        subjects[item] = subject
        matches = [r for r in receipts if r.get("stage") == item]
        if not matches or not all(not receipt_mismatches(r, packet, conversation_id, subject) for r in matches):
            reasons.append(f"{item}の現在内容に一致する人間承認が必要です")
    if not reasons:
        result["status"] = "approved"
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
