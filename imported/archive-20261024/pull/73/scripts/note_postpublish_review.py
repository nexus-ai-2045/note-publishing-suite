#!/usr/bin/env python3
"""公開本文のlint・実行照合・既存feedback保存を分離する共通入口。"""
from __future__ import annotations

from datetime import datetime
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
from typing import Callable

from note_feedback import article_directory, read_article_feedback, read_feedback_record, record_feedback
from pre_publish_check import collect_published_issues as collect_issues
from sync_note_public_snapshot import extract_note_id, ledger_file_lock

RuntimeVerifier = Callable[[dict, bytes], bool]
AUTHENTICITY = "JSONはAI実行の真正性を証明しません。実結果と実IDの照合はtrusted runtimeが所有します。"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.strip().casefold() not in {
        "unknown", "todo", "pending", "none", "null", "未確認", "未定", "保留"}


def _validate_ai(review: dict, observed: dict, base_dir: Path) -> tuple[list[dict], Path, bytes]:
    body = observed["body"]
    body_hash = digest(body.encode("utf-8"))
    if (review.get("note_id") != observed["note_id"] or review.get("url") != observed["url"]
            or review.get("body_sha256") != body_hash):
        raise ValueError("AI点検の対象記事または本文hashが一致しません")
    if (review.get("scope") != "full_public_body" or type(review.get("coverage_start")) is not int
            or type(review.get("coverage_end")) is not int
            or review["coverage_start"] != 0 or review["coverage_end"] != len(body)):
        raise ValueError("AI点検が公開本文の全範囲に対応していません")
    checks = review.get("checks")
    if (not isinstance(checks, list) or len(checks) != 4
            or any(not isinstance(item, str) for item in checks)
            or set(checks) != {"typos", "omissions", "readability", "voice_preservation"}):
        raise ValueError("誤字・脱字・読みやすさ・本人の語り口の点検項目が不足しています")
    if (not _text(review.get("source_thread_id"))
            or not any(_text(review.get(key)) for key in ("worker_id", "turn_id"))
            or not _text(review.get("summary"))):
        raise ValueError("AI点検の実行ID・実点検結果が不足しています")
    if not _text(review.get("reviewed_at")):
        raise ValueError("AI点検の実行日時が必要です")
    stamp = datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
    if stamp.utcoffset() is None:
        raise ValueError("AI点検日時にはtimezoneが必要です")
    findings = review.get("findings")
    if not isinstance(findings, list):
        raise ValueError("AI点検findingsは配列で明示してください")
    for item in findings:
        if (not isinstance(item, dict) or any(not _text(item.get(key)) for key in ("before", "after", "reason"))
                or item["before"] not in body or item["before"] == item["after"]
                or item.get("origin", "ai") != "ai" or item.get("decision", "pending") != "pending"):
            raise ValueError("AI候補は現在本文の引用と修正案・理由を持つai/pendingだけを受け入れます")
    if not _text(review.get("evidence_ref")):
        raise ValueError("AI実回答の証拠参照が必要です")
    evidence = (base_dir / review["evidence_ref"]).resolve(strict=True)
    raw = evidence.read_bytes()
    if review.get("evidence_sha256") != digest(raw):
        raise ValueError("AI実回答の証拠hashが一致しません")
    expected = {key: value for key, value in review.items() if key not in {"evidence_ref", "evidence_sha256"}}
    if json.loads(raw) != expected:
        raise ValueError("AI実回答と観測内の点検結果が一致しません")
    return findings, evidence, raw


def check_postpublish_review(observed: dict | None, *, base_dir: Path = Path("."),
                             runtime_verifier: RuntimeVerifier | None = None,
                             feedback_context: dict | None = None,
                             write_feedback: bool = False) -> dict:
    """runtime_verifierは実tool回収ownerが供給する。CLIの自己申告flagで代用しない。"""
    result = {"status": "waiting_for_publication", "postpublication_complete": False,
              "mechanical": {"status": "not_run"}, "ai_review": {"status": "not_run"},
              "feedback": {"status": "not_saved"}, "authenticity_notice": AUTHENTICITY,
              "external_actions": [], "body_changes": []}
    if observed is None:
        return result
    try:
        observation_bytes = json.dumps(observed, sort_keys=True, ensure_ascii=False).encode("utf-8")
        if (not isinstance(observed, dict) or observed.get("schema") != "note-public-observation/v1"
                or not _text(observed.get("body"))
                or extract_note_id(observed["url"]) != observed.get("note_id")):
            raise ValueError("公開観測の対象または本文が不正です")
        body_hash = digest(observed["body"].encode("utf-8"))
        if observed.get("body_sha256", body_hash) != body_hash:
            raise ValueError("公開観測本文hashが一致しません")
        result.update(status="postpublish_review_pending", note_id=observed["note_id"], body_sha256=body_hash)
        issues = collect_issues(observed["body"])
        result["mechanical"] = {"status": "checked", "input_format": "published_plain", "body_sha256": body_hash, "issues": issues}
        if any(item.get("code") == "secret_like_value" for item in issues):
            raise ValueError("秘密情報候補を検出したためfeedbackへの本文複製を停止します")
        review = observed.get("editorial_review")
        if not isinstance(review, dict):
            result["next_action"] = "trusted runtimeが公開本文全体を読み実点検結果を回収する"
            return result
        findings, evidence, raw = _validate_ai(review, observed, base_dir)
        result["ai_review"] = {"status": "runtime_confirmation_required", "finding_count": len(findings)}
        if runtime_verifier is None:
            result["next_action"] = "実tool結果と実行IDを回収したruntimeで照合する"
            return result
        if runtime_verifier(review, raw) is not True:
            raise ValueError("trusted runtimeがAI実行結果を確認できません")
        if (evidence.read_bytes() != raw
                or json.dumps(observed, sort_keys=True, ensure_ascii=False).encode("utf-8") != observation_bytes):
            raise ValueError("実行照合中にAI実回答が変更されました")
        result["ai_review"].update(status="execution_attested", evidence_sha256=digest(raw))
        if not isinstance(feedback_context, dict):
            result["next_action"] = "既存feedbackへAI候補を保存して読戻す"
            return result
        dirs, source, draft, prior, conversation = (feedback_context[key] for key in
            ("dirs", "source", "draft", "prior", "conversation_id"))
        if conversation != review["source_thread_id"]:
            raise ValueError("feedbackの会話とAI実行元の会話が一致しません")
        note_id = observed["note_id"]
        base = article_directory(dirs, note_id)
        # 同じwriterを使い、既存entryの採否と履歴snapshotを保全する。
        with ledger_file_lock(base / "feedback.json") if write_feedback else nullcontext():
            old_entries = []
            existing_readback = None
            if (base / "feedback.json").exists():
                record, _ = read_feedback_record(dirs, note_id)
                existing_readback = read_article_feedback(dirs, note_id, source, draft)
                old_entries = record["entries"]
            additions = [{"origin": "ai", "decision": "pending", "before": row["before"],
                          "after": row["after"], "reason": row["reason"],
                          "evidence_ref": str(evidence)} for row in findings]
            entries = list(old_entries)
            for entry in additions:
                # 同じ提案の再点検で実回答fileが変わっても候補を増やさない。
                # 元候補の証拠は保持し、今回の実点検証拠は観測側へ残す。
                key = tuple(entry[field] for field in ("origin", "decision", "before", "after"))
                if not any(tuple(old[field] for field in ("origin", "decision", "before", "after")) == key
                           for old in entries):
                    entries.append(entry)
            if not write_feedback and (existing_readback is None or entries != old_entries):
                result["feedback"] = {"status": "save_required", "planned_additions": len(entries) - len(old_entries)}
                return result
            readback = (existing_readback if existing_readback is not None and entries == old_entries
                        else record_feedback(dirs, note_id, source, draft, prior, entries, conversation_id=conversation))
            saved, verified = read_feedback_record(dirs, note_id)
            if (saved["entries"] != entries or verified != readback
                    or read_article_feedback(dirs, note_id, source, draft) != readback):
                raise ValueError("feedback保存の読戻しが一致しません")
            if (evidence.read_bytes() != raw
                    or json.dumps(observed, sort_keys=True, ensure_ascii=False).encode("utf-8") != observation_bytes):
                raise ValueError("feedback保存中にAI実回答が変更されました")
        unresolved = [entry for entry in saved["entries"] if entry["decision"] == "pending"
                      and _text(entry["before"]) and _text(entry["after"])
                      and entry["before"] != entry["after"] and entry["before"] in observed["body"]]
        result["feedback"] = {"status": "saved_verified", "readback": readback,
                              "unresolved_body_proposals": unresolved}
        if findings or unresolved or any(item.get("severity") == "error" for item in issues):
            result["status"] = "review_required"
            result["next_action"] = "AI/pending候補と機械検査の指摘を本人へ提示する。本文は自動修正しない"
        else:
            result.update(status="checked", postpublication_complete=True)
        return result
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        result.update(status="blocked", error=str(exc), postpublication_complete=False)
        return result
