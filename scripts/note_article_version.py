#!/usr/bin/env python3
"""note公開記事の版を既存 published_notes 台帳でprepare/finalize/cancelする。"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def find_default_ledger() -> Path:
    """repo-local package copyからも公開台帳を解決する。"""
    for base in (ROOT, *ROOT.parents):
        candidate = base / "data" / "published_notes.json"
        if candidate.is_file():
            return candidate
    return ROOT / "data" / "published_notes.json"


LEDGER = find_default_ledger()
VERSION_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
TITLE_VERSION_RE = re.compile(r"(?:\s*[（(｜|]\s*v\d+\.\d+\.\d+\s*[）)]?)$")


def bump(version: str, part: str) -> str:
    match = VERSION_RE.fullmatch(version)
    if not match:
        raise ValueError(f"invalid version: {version}")
    major, minor, patch = map(int, match.groups())
    if part == "major":
        return f"v{major + 1}.0.0"
    if part == "minor":
        return f"v{major}.{minor + 1}.0"
    return f"v{major}.{minor}.{patch + 1}"


def versioned_title(title: str, version: str) -> str:
    base = TITLE_VERSION_RE.sub("", title).rstrip()
    return f"{base}({version})"


def find_record(records: list[dict], note_id: str) -> dict:
    matches = [item for item in records if item.get("note_id") == note_id]
    if len(matches) != 1:
        raise ValueError(f"note_id must match exactly one record: {note_id} ({len(matches)})")
    return matches[0]


def prepare(record: dict, part: str, initial: str, reason: str) -> dict:
    if record.get("pending_version"):
        raise ValueError(f"pending version already exists: {record['pending_version']}")
    current = record.get("version") or initial
    next_version = bump(current, part)
    record["version"] = current
    record["pending_version"] = next_version
    record["pending_title"] = versioned_title(record["title"], next_version)
    record["version_status"] = "prepared"
    record["version_reason"] = reason
    record["version_prepared_at"] = datetime.now().astimezone().isoformat()
    return record


def finalize(record: dict, observed_title: str) -> dict:
    pending = record.get("pending_version")
    if not pending:
        raise ValueError("pending_version is missing")
    expected_title = record.get("pending_title")
    if not expected_title:
        raise ValueError("pending_title is missing")
    if observed_title != expected_title:
        raise ValueError(f"observed title does not exactly match pending_title: {observed_title}")
    history = record.setdefault("version_history", [])
    history.append(
        {
            "version": pending,
            "title": observed_title,
            "finalized_at": datetime.now().astimezone().isoformat(),
            "reason": record.get("version_reason"),
        }
    )
    record["version"] = pending
    record["title"] = observed_title
    record["version_status"] = "published"
    for key in ("pending_version", "pending_title", "version_reason", "version_prepared_at"):
        record.pop(key, None)
    return record


def cancel(record: dict, reason: str) -> dict:
    """未公開のpending版を取り消し、公開済み版を変更せずに履歴を残す。"""
    pending = record.get("pending_version")
    if not pending:
        raise ValueError("pending_version is missing")
    if not reason.strip():
        raise ValueError("cancel reason must not be empty")

    cancellations = record.setdefault("version_cancellation_history", [])
    cancellations.append(
        {
            "version": pending,
            "title": record.get("pending_title"),
            "cancelled_at": datetime.now().astimezone().isoformat(),
            "reason": reason,
            "prepared_at": record.get("version_prepared_at"),
            "prepare_reason": record.get("version_reason"),
        }
    )
    for key in ("pending_version", "pending_title", "version_reason", "version_prepared_at"):
        record.pop(key, None)
    if record.get("version"):
        record["version_status"] = "published"
    else:
        record.pop("version_status", None)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--note-id", required=True)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="action", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--part", choices=("major", "minor", "patch"), default="patch")
    prepare_parser.add_argument("--initial", default="v0.1.0")
    prepare_parser.add_argument("--reason", required=True)
    finalize_parser = sub.add_parser("finalize")
    finalize_parser.add_argument("--observed-title", required=True)
    for action in ("cancel", "abort"):
        cancel_parser = sub.add_parser(action)
        cancel_parser.add_argument("--reason", required=True)
    args = parser.parse_args()

    records = json.loads(args.ledger.read_text(encoding="utf-8"))
    record = find_record(records, args.note_id)
    if args.action == "prepare":
        prepare(record, args.part, args.initial, args.reason)
    elif args.action == "finalize":
        finalize(record, args.observed_title)
    else:
        cancel(record, args.reason)

    if not args.dry_run:
        args.ledger.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
