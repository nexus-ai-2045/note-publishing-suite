#!/usr/bin/env python3
"""Prepare or write local Note publication ledger entries.

Default operation is dry-run. Use --write-ledger to change JSON ledgers.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLISHED_LEDGER = ROOT / "data" / "published_notes.json"
DRAFT_LEDGER = ROOT / "data" / "note_drafts.json"


def load_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def write_list(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--draft", required=True, type=Path)
    parser.add_argument("--title")
    parser.add_argument("--published-at")
    parser.add_argument("--tags", default="")
    parser.add_argument("--image-url", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-ledger", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.write_ledger:
        args.dry_run = True

    entry = {
        "url": args.url,
        "title": args.title or args.draft.stem,
        "published_at": args.published_at or datetime.now(timezone.utc).isoformat(),
        "tags": [t.strip() for t in args.tags.split(",") if t.strip()],
        "image_url": args.image_url,
        "local_source": str(args.draft),
        "source": "note-publishing-suite",
        "plain_status": "published_or_scheduled_unverified" if args.dry_run else "published_or_scheduled",
    }

    result = {"mode": "dry-run" if args.dry_run else "write-ledger", "published_entry": entry}
    if args.write_ledger:
        published = load_list(PUBLISHED_LEDGER)
        published = [row for row in published if row.get("url") != args.url]
        published.append(entry)
        write_list(PUBLISHED_LEDGER, published)

        drafts = load_list(DRAFT_LEDGER)
        drafts.append({"draft": str(args.draft), "status": "published_from_note_editor_record", "url": args.url})
        write_list(DRAFT_LEDGER, drafts)
        result["updated_ledgers"] = [str(PUBLISHED_LEDGER), str(DRAFT_LEDGER)]

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
