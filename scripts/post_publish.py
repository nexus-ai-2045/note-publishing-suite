#!/usr/bin/env python3
"""Prepare or write local Note publication ledger entries.

Default operation is dry-run. Use --write-ledger to change JSON ledgers.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER_DIR = ROOT / "data"


def load_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def write_list(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def same_draft(row: dict, draft: Path, note_id: str | None) -> bool:
    if note_id and row.get("note_id") == note_id:
        return True
    row_draft = str(row.get("draft") or row.get("local_source") or "")
    if not row_draft:
        return False
    return Path(row_draft).name == draft.name


def upsert_draft_transition(
    rows: list[dict],
    *,
    draft: Path,
    note_id: str | None,
    url: str,
    published_at: str,
    title: str,
    snapshot: str,
    body_sha256: str,
) -> list[dict]:
    transition = {
        "draft": str(draft),
        "status": "published_from_note_editor_record",
        "published_url": url,
        "published_at": published_at,
        "published_title": title,
    }
    if note_id:
        transition["note_id"] = note_id
    if snapshot:
        transition["published_snapshot"] = snapshot
    if body_sha256:
        transition["published_body_sha256"] = body_sha256

    updated: list[dict] = []
    matched = False
    for row in rows:
        if same_draft(row, draft, note_id):
            updated.append({**row, **transition})
            matched = True
        else:
            updated.append(row)
    if not matched:
        updated.append(transition)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--draft", required=True, type=Path)
    parser.add_argument("--title")
    parser.add_argument("--published-at")
    parser.add_argument("--tags", default="")
    parser.add_argument("--image-url", default="")
    parser.add_argument("--note-id")
    parser.add_argument("--verified-at")
    parser.add_argument("--published-snapshot", default="")
    parser.add_argument("--published-body-sha256", default="")
    parser.add_argument("--local-draft-differs-from-published", action="store_true")
    parser.add_argument("--cover-image-verified", action="store_true")
    parser.add_argument(
        "--verification-status",
        choices=["published_verified", "scheduled_verified", "published_or_scheduled_unverified"],
        default="published_or_scheduled_unverified",
    )
    parser.add_argument(
        "--ledger-dir",
        type=Path,
        default=DEFAULT_LEDGER_DIR,
        help="Directory containing note_drafts.json and published_notes.json.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write-ledger", action="store_true")
    args = parser.parse_args()

    if args.verification_status != "published_or_scheduled_unverified" and not args.verified_at:
        parser.error("--verified-at is required for a verified publication status")
    if args.published_body_sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", args.published_body_sha256):
        parser.error("--published-body-sha256 must be a 64-character hexadecimal SHA-256")

    if not args.dry_run and not args.write_ledger:
        args.dry_run = True

    published_at = args.published_at or datetime.now(timezone.utc).isoformat()
    title = args.title or args.draft.stem
    entry = {
        "url": args.url,
        "title": title,
        "published_at": published_at,
        "tags": [t.strip() for t in args.tags.split(",") if t.strip()],
        "image_url": args.image_url,
        "local_source": str(args.draft),
        "source": "note-publishing-suite",
        "plain_status": args.verification_status,
    }
    if args.note_id:
        entry["note_id"] = args.note_id
    if args.verified_at:
        entry["verified_at"] = args.verified_at
    if args.published_snapshot:
        entry["published_snapshot"] = args.published_snapshot
    if args.published_body_sha256:
        entry["published_body_sha256"] = args.published_body_sha256
    if args.local_draft_differs_from_published:
        entry["local_draft_differs_from_published"] = True
    if args.cover_image_verified:
        entry["cover_image_verified"] = True

    result = {"mode": "dry-run" if args.dry_run else "write-ledger", "published_entry": entry}
    if args.write_ledger:
        published_ledger = args.ledger_dir / "published_notes.json"
        draft_ledger = args.ledger_dir / "note_drafts.json"
        published = load_list(published_ledger)
        published = [row for row in published if row.get("url") != args.url]
        published.append(entry)
        write_list(published_ledger, published)

        drafts = upsert_draft_transition(
            load_list(draft_ledger),
            draft=args.draft,
            note_id=args.note_id,
            url=args.url,
            published_at=published_at,
            title=title,
            snapshot=args.published_snapshot,
            body_sha256=args.published_body_sha256,
        )
        write_list(draft_ledger, drafts)
        result["updated_ledgers"] = [str(published_ledger), str(draft_ledger)]

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
