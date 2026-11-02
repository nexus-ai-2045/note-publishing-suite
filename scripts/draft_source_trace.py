#!/usr/bin/env python3
"""List draft sentences that cannot be traced to the author's own words.

The draft is split into sentences. Each sentence is compared with the author's
source texts (original messages, transcripts) and, when a topic ledger is
given, with the author-owned ledger fields (evidence of user_speech and
external_source topics, author_explanation and author_reaction). A sentence whose character
bigrams mostly do not appear in those sources is listed as "not in the
original" for the author to keep, rewrite or delete. AI suggestion evidence is
not counted as a source, so AI wording stays visible.

This is a review list, not proof of authorship: a faithful paraphrase can be
listed, and a copied phrase can hide a changed meaning.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "note-draft-source-trace/v1"
DEFAULT_THRESHOLD = 0.5
AUTHOR_ORIGINS = {"user_speech", "external_source"}
SENTENCE_END_RE = re.compile(r"(?<=[。！？!?])")
LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
URL_RE = re.compile(r"https?://\S+")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
SKIP_LINE_RE = re.compile(r"^\s*(#|>|<!--|\||---\s*$|!\[)")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return "".join(ch for ch in text if ch.isalnum())


def _bigrams(text: str) -> set[str]:
    return {text[i:i + 2] for i in range(len(text) - 1)}


def draft_sentences(text: str) -> list[dict[str, Any]]:
    """Body sentences with line numbers; skips front matter, code, headings, quotes, markers."""
    lines = text.splitlines()
    start = 0
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                start = index + 1
                break
    sentences: list[dict[str, Any]] = []
    in_fence = False
    for number, line in enumerate(lines[start:], start=start + 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or not line.strip() or SKIP_LINE_RE.match(line):
            continue
        plain = URL_RE.sub("", LINK_RE.sub(r"\1", line)).replace("**", "").strip(" -*\t")
        for part in SENTENCE_END_RE.split(plain):
            if len(_normalize(part)) >= 4:
                sentences.append({"line": number, "text": part.strip()})
    return sentences


def ledger_sources(ledger: Any) -> list[str]:
    texts: list[str] = []
    topics = ledger.get("topics") if isinstance(ledger, dict) else None
    for topic in topics if isinstance(topics, list) else []:
        if not isinstance(topic, dict):
            continue
        if topic.get("origin") in AUTHOR_ORIGINS and isinstance(topic.get("evidence"), str):
            texts.append(topic["evidence"])
        for key in ("author_explanation", "author_reaction"):
            if isinstance(topic.get(key), str):
                texts.append(topic[key])
    return texts


def evaluate(draft: str, sources: list[str], threshold: float = DEFAULT_THRESHOLD) -> dict[str, Any]:
    pool: set[str] = set()
    for source in sources:
        pool |= _bigrams(_normalize(source))
    rows = []
    for sentence in draft_sentences(draft):
        grams = _bigrams(_normalize(sentence["text"]))
        coverage = len(grams & pool) / len(grams) if grams else 1.0
        rows.append({**sentence, "coverage": round(coverage, 2)})
    unsourced = [row for row in rows if row["coverage"] < threshold]
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "threshold": threshold,
        "source_count": len(sources),
        "sentence_count": len(rows),
        "unsourced_count": len(unsourced),
        "unsourced_sentences": unsourced,
        "guarantee_scope": "character_bigram_overlap_only; author_review_required",
        "external_actions_performed": [],
    }


def to_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# 原文にない文の一覧",
        "",
        f"本文 {result['sentence_count']} 文のうち、本人の原文と重なりが"
        f" {int(result['threshold'] * 100)}% 未満の文が {result['unsourced_count']} 文あります。",
        "それぞれ「残す・直す・消す」を本人が決めます。言い換えとして正しい文も載ることがあります。",
        "",
    ]
    for row in result["unsourced_sentences"]:
        lines.append(f"- [ ] {row['line']}行目（重なり {int(row['coverage'] * 100)}%）: {row['text']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path)
    parser.add_argument("--source", type=Path, action="append", default=[],
                        help="本人の原文ファイル（複数可）")
    parser.add_argument("--ledger", type=Path, help="論点台帳（本人の言葉の evidence を原文に加える）")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--markdown", type=Path, help="本人向けの一覧を書き出す先")
    args = parser.parse_args()
    sources = [path.read_text(encoding="utf-8") for path in args.source]
    if args.ledger:
        sources += ledger_sources(json.loads(args.ledger.read_text(encoding="utf-8")))
    if not sources:
        print(json.dumps({"schema_version": SCHEMA_VERSION, "ok": False,
                          "stop_causes": ["no author source given"]}, ensure_ascii=False))
        return 1
    result = evaluate(args.draft.read_text(encoding="utf-8"), sources, args.threshold)
    if args.markdown:
        args.markdown.write_text(to_markdown(result), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
