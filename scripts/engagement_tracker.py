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
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["report"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    drafts = load(ROOT / "data" / "note_drafts.json")
    published = load(ROOT / "data" / "published_notes.json")
    result = {
        "draft_count": len(drafts) if isinstance(drafts, list) else 0,
        "published_count": len(published) if isinstance(published, list) else 0,
        "external_access": "none",
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"draft_count={result['draft_count']}")
        print(f"published_count={result['published_count']}")
        print("external_access=none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
