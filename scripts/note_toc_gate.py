#!/usr/bin/env python3
"""Fail closed when a production Note draft is missing a usable live TOC."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def validate(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(data, dict) or data.get("article_lane") not in (
        "production_candidate", "exploratory_draft", "editor_fixture", "continuation_article"
    ):
        return [{"code": "invalid_article_lane", "message": "対象の記事laneが欠落または不正です"}]
    if data["article_lane"] != "production_candidate":
        return issues

    h2_count = data.get("h2_count")
    h3_count = data.get("h3_count")
    toc_count = data.get("toc_count")
    toc_ref_count = data.get("toc_ref_count")

    if type(h2_count) is not int or h2_count < 2:
        issues.append({"code": "headings_missing", "message": "大見出し（H2）が2件以上必要です"})
    if type(h3_count) is not int or h3_count < 0:
        issues.append({"code": "heading_count_invalid", "message": "小見出し（H3）の件数が不正です"})
    if type(toc_count) is not int or toc_count != 1:
        issues.append({"code": "toc_missing", "message": "Note固有の目次ブロックが正確に1件必要です"})

    heading_total = (
        h2_count + h3_count
        if type(h2_count) is int and type(h3_count) is int
        else None
    )
    if heading_total is None or type(toc_ref_count) is not int or toc_ref_count != heading_total:
        issues.append({"code": "toc_refs_incomplete", "message": "目次がH2/H3見出しをすべて参照していません"})
    if data.get("toc_before_first_heading") is not True:
        issues.append({"code": "toc_position_invalid", "message": "目次は導入文の後、最初の見出しの前に置いてください"})
    if data.get("toc_contenteditable") != "false":
        issues.append({"code": "toc_dom_invalid", "message": "table-of-contents contenteditable=false を確認できません"})
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("observation", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.observation.read_text(encoding="utf-8"))
    issues = validate(data)
    payload = {
        "ok": not issues,
        "ready_for_draft_save": not issues,
        "issues": issues,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.json else 2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
