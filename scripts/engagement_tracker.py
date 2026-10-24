#!/usr/bin/env python3
"""Report local Note ledger status without external access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(path: Path):
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("台帳はobject配列である必要があります")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["report"])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--ledger-dir", type=Path, required=True, help="採用した外部台帳のディレクトリ")
    args = parser.parse_args(argv)
    ledger_dir = args.ledger_dir.resolve()
    if not ledger_dir.is_dir():
        parser.error("--ledger-dirは既存の台帳ディレクトリを指定してください")

    drafts = load(ledger_dir / "note_drafts.json")
    published = load(ledger_dir / "published_notes.json")
    result = {
        "draft_count": len(drafts) if isinstance(drafts, list) else 0,
        "published_count": len(published) if isinstance(published, list) else 0,
        "external_access": "none",
        "ledger_dir": str(ledger_dir),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(f"draft_count={result['draft_count']}")
        print(f"published_count={result['published_count']}")
        print("external_access=none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
