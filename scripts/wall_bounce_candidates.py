#!/usr/bin/env python3
"""Pick AI answers the author seemed to accept during a wall-bounce conversation.

Input is a JSON list of turns: [{"role": "assistant" | "user", "text": "..."}].
When an author turn right after an AI turn contains an agreement word
("確かに", "なるほど", ...), the AI answer becomes an "accepted" candidate. When
the author turn is a follow-up question ("じゃあこうなの？"), it becomes a
"question" candidate: a question is not agreement yet and must be confirmed.

Candidates are only a list to ask the author about, three at a time. Nothing
here decides that the author agreed; the ledger records it only after the
author restates the idea in their own words (author_explanation).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "note-wall-bounce-candidates/v1"
AGREEMENT_WORDS = ("確かに", "たしかに", "なるほど", "そうだね", "そうだよね", "それだ", "それな", "そうそう", "納得")
QUESTION_END_RE = re.compile(r"[?？]\s*$")


def candidates(turns: Any) -> list[dict[str, Any]]:
    if not isinstance(turns, list):
        raise ValueError("turns must be a JSON array")
    found: list[dict[str, Any]] = []
    for index in range(1, len(turns)):
        before, after = turns[index - 1], turns[index]
        if not (isinstance(before, dict) and isinstance(after, dict)):
            continue
        if before.get("role") != "assistant" or after.get("role") != "user":
            continue
        reaction = str(after.get("text", "")).strip()
        if any(word in reaction for word in AGREEMENT_WORDS):
            kind = "accepted"
        elif QUESTION_END_RE.search(reaction):
            kind = "question"
        else:
            continue
        found.append({"turn": index, "kind": kind, "ai_answer": str(before.get("text", "")).strip(),
                      "author_reaction": reaction})
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("turns", type=Path, help="会話のターンのJSON")
    args = parser.parse_args()
    rows = candidates(json.loads(args.turns.read_text(encoding="utf-8")))
    print(json.dumps({"schema_version": SCHEMA_VERSION, "ok": True, "candidate_count": len(rows),
                      "candidates": rows, "next": "3件ずつ本人に見せ、入ったかと自分の言葉を聞く",
                      "external_actions_performed": []}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
