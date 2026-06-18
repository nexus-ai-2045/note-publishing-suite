#!/usr/bin/env python3
"""Run local pre-publication checks for a Note draft."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any


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

PUBLICATION_DATE_KEYS = {
    "publish_at",
    "publish_date",
    "published_at",
    "publication_at",
    "publication_date",
    "scheduled_at",
    "scheduled_publish_at",
    "target_publish_at",
}

ISO_DATE_PATTERN = re.compile(r"\b(20\d{2})-(0[1-9]|1[0-2])-([0-2]\d|3[01])\b")
JAPANESE_DATE_PATTERN = re.compile(r"\b(20\d{2})年(1[0-2]|0?[1-9])月(3[01]|[12]\d|0?[1-9])日")
RECHECK_REQUIRED_PATTERN = re.compile(
    r"(公開時|公開時点|記事公開時|公開前|投稿時|投稿時点).{0,16}(再確認|要確認)"
    r"|(?:再確認|要確認).{0,16}(公開時|公開時点|記事公開時|公開前|投稿時|投稿時点)"
)


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text

    metadata: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip().strip("'\"")
    return metadata, text[end + len("\n---") :]


def parse_date(value: str) -> date | None:
    match = ISO_DATE_PATTERN.search(value)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None

    match = JAPANESE_DATE_PATTERN.search(value)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    return None


def publication_date_from_metadata(metadata: dict[str, str]) -> date | None:
    for key in PUBLICATION_DATE_KEYS:
        value = metadata.get(key)
        if not value:
            continue
        parsed = parse_date(value)
        if parsed:
            return parsed
    return None


def find_future_date_issues(body: str, publication_date: date | None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not publication_date:
        return issues

    seen: set[tuple[int, str]] = set()
    for line_no, line in enumerate(body.splitlines(), 1):
        for pattern in (ISO_DATE_PATTERN, JAPANESE_DATE_PATTERN):
            for match in pattern.finditer(line):
                parsed = parse_date(match.group(0))
                if not parsed or parsed <= publication_date:
                    continue
                key = (line_no, match.group(0))
                if key in seen:
                    continue
                seen.add(key)
                issues.append(
                    {
                        "severity": "warning",
                        "code": "future_dated_claim",
                        "message": (
                            f"date {match.group(0)} is after publication date "
                            f"{publication_date.isoformat()}"
                        ),
                        "line": line_no,
                        "date": match.group(0),
                        "publication_date": publication_date.isoformat(),
                        "snippet": line.strip()[:180],
                    }
                )
    return issues


def find_recheck_issues(body: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for line_no, line in enumerate(body.splitlines(), 1):
        if not RECHECK_REQUIRED_PATTERN.search(line):
            continue
        issues.append(
            {
                "severity": "warning",
                "code": "publish_time_recheck_required",
                "message": "publication-time recheck marker found",
                "line": line_no,
                "snippet": line.strip()[:180],
            }
        )
    return issues


def collect_issues(text: str) -> list[dict[str, Any]]:
    metadata, body = split_frontmatter(text)
    publication_date = publication_date_from_metadata(metadata)
    issues: list[dict[str, Any]] = []
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
    issues.extend(find_future_date_issues(body, publication_date))
    issues.extend(find_recheck_issues(body))
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
