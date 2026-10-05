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


def read_article_feedback(dirs: dict[str, Path], article_id: str, source: Path, draft: Path) -> dict:
    """保存先をpacketから受け取らず、設定から独立に解決して読み直す。"""
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
    if digest(source.read_bytes()) != hashes["source"] or digest(draft.read_bytes()) != hashes["draft"]:
        raise ValueError("履歴が現在の原資料・原稿と一致しません")
    difference = confined(base, "note-vs-local-diff.md").read_bytes()
    if digest(difference) != record.get("diff_sha256") or difference != diff_bytes(snapshots["prior"], snapshots["draft"]):
        raise ValueError("差分記録がsnapshotと一致しません")
    return {"record_sha256": digest(raw), "diff_sha256": digest(difference), "snapshot_hashes": hashes}


def main() -> int:
    parser = argparse.ArgumentParser(description="本人の採否履歴を外部SSOTへ保全する（公開操作なし）")
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--article-id", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--prior-draft", type=Path, required=True)
    parser.add_argument("--entries", type=Path, required=True)
    parser.add_argument("--conversation-id", required=True)
    args = parser.parse_args()
    from note_workflow_gate import read_workspace_settings
    try:
        _, dirs = read_workspace_settings(args.settings, args.article_id)
        result = record_feedback(dirs, args.article_id, args.source, args.draft, args.prior_draft,
                                 json.loads(args.entries.read_text(encoding="utf-8")), conversation_id=args.conversation_id)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "recorded", "feedback_readback": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
