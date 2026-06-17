#!/usr/bin/env python3
"""Run local pre-publication checks for a Note draft."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]

WARNING_PATTERNS = {
    "html_comment": re.compile(r"<!--.*?-->", re.S),
    "todo_marker": re.compile(r"\b(TODO|FIXME)\b", re.I),
    "uncertain_japanese": re.compile(r"(未確認|要確認|仮置き|あとで|TODO|内部メモ)"),
    "private_url_hint": re.compile(r"(localhost|127\.0\.0\.1|file://|C:\\\\Users|/Users/)"),
}


def collect_issues(text: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            issues.append({"severity": "error", "code": "secret_like_value", "message": "secret-like value found"})
    for code, pattern in WARNING_PATTERNS.items():
        if pattern.search(text):
            issues.append({"severity": "warning", "code": code, "message": f"{code} found"})
    if not re.search(r"^#\s+\S+", text, re.M):
        issues.append({"severity": "warning", "code": "missing_h1", "message": "draft has no H1 title"})
    if len(text.strip()) < 400:
        issues.append({"severity": "warning", "code": "short_draft", "message": "draft is very short"})
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("--fix", action="store_true", help="Remove HTML comments only; other issues remain manual.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    text = args.draft.read_text(encoding="utf-8")
    if args.fix:
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        args.draft.write_text(text, encoding="utf-8", newline="\n")

    issues = collect_issues(text)
    result = {
        "draft": str(args.draft),
        "overall": "error" if any(i["severity"] == "error" for i in issues) else ("warning" if issues else "ok"),
        "issues": issues,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"overall={result['overall']}")
        for issue in issues:
            print(f"{issue['severity']}:{issue['code']} {issue['message']}")
    return 1 if result["overall"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
