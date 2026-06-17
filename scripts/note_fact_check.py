#!/usr/bin/env python3
"""Find local fact-check candidates in a Note draft."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PATTERNS = {
    "uncertain_claim": re.compile(r"(未確認|要確認|推測|多分|おそらく|らしい|かもしれない)"),
    "number_or_percent": re.compile(r"(\d[\d,]*(?:\.\d+)?\s*(?:%|円|人|件|年|月|日)?)"),
    "url": re.compile(r"https?://[^\s)]+"),
    "internal_note": re.compile(r"(内部メモ|下書きメモ|TODO|FIXME)", re.I),
    "personal_experience_claim": re.compile(
        r"(私|僕|俺|自分|わたし|ぼく).{0,24}(感じた|思った|考えた|体験|経験|見た|聞いた|試した|やってみた|気づいた)"
        r"|(?:体験|経験|実感|自分の発言|自分の言葉|本人の言葉|発言ベース|体験ベース)"
    ),
    "source_provenance_marker": re.compile(
        r"(source|出典|出典ノート|根拠|引用元|発言ログ|会話ログ|素材|体験メモ|原文)"
    ),
}


def scan(text: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for code, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append({"line": line_no, "code": code, "text": line.strip()[:180]})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["local"])
    parser.add_argument("draft", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    findings = scan(args.draft.read_text(encoding="utf-8"))
    result = {"draft": str(args.draft), "mode": args.mode, "finding_count": len(findings), "findings": findings}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"finding_count={len(findings)}")
        for item in findings:
            print(f"line={item['line']} code={item['code']} text={item['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
