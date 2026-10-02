#!/usr/bin/env python3
"""Validate live Note editor line-break structure before draft save."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def validate(data: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if data.get("article_lane") != "production_candidate":
        return errors, warnings

    trailing = data.get("trailing_plain_br_count")
    consecutive_empty = data.get("consecutive_empty_paragraph_count")
    literal_backslash = data.get("literal_backslash_linebreak_count")
    empty = data.get("empty_paragraph_count")
    empty_before_figure = data.get("empty_paragraph_before_figure_count")
    multi = data.get("paragraphs_with_multiple_plain_br_count")

    if trailing != 0:
        errors.append(issue("trailing_plain_br", "文字の末尾に不要な通常brが残っています"))
    if consecutive_empty != 0:
        errors.append(issue("consecutive_empty_paragraphs", "空段落が連続しています"))
    if literal_backslash != 0:
        errors.append(issue("literal_backslash_linebreak", "改行の代わりにバックスラッシュが表示されています"))
    if not isinstance(empty, int) or empty < 0:
        errors.append(issue("empty_paragraph_count_missing", "空段落数の実測が必要です"))
    elif empty > 0:
        warnings.append(issue("empty_paragraphs_review", f"単独の空段落が{empty}件あります。画像・埋め込み周辺か目視確認してください"))
    if not isinstance(empty_before_figure, int) or empty_before_figure < 0:
        errors.append(
            issue(
                "empty_paragraph_before_figure_count_missing",
                "図の直前にある空段落数の実測が必要です",
            )
        )
    elif empty_before_figure > 0:
        errors.append(
            issue(
                "empty_paragraph_before_figure",
                f"図の直前に空段落が{empty_before_figure}件あります",
            )
        )
    if isinstance(multi, int) and multi > 0:
        warnings.append(issue("multiple_linebreaks_review", f"段落内に複数の通常brを含む段落が{multi}件あります。意図した読みやすさ調整か確認してください"))
    if any(field in data for field in ("expected_paragraph_soft_break_counts", "paragraph_soft_break_counts")):
        expected = data.get("expected_paragraph_soft_break_counts")
        observed = data.get("paragraph_soft_break_counts")
        structure_valid = True
        for field, counts in (
            ("expected_paragraph_soft_break_counts", expected),
            ("paragraph_soft_break_counts", observed),
        ):
            if not isinstance(counts, list) or any(
                type(count) is not int or count < 0 for count in counts
            ):
                structure_valid = False
                errors.append(issue(f"{field}_invalid", f"{field}は本文段落順の0以上の整数配列で指定してください"))
        if structure_valid and observed != expected:
            errors.append(issue("source_paragraph_structure_mismatch", "本文の段落境界または段落内改行が原稿の期待構造と一致しません"))
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("observation", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.observation.read_text(encoding="utf-8"))
    errors, warnings = validate(data)
    payload = {
        "ok": not errors,
        "ready_for_draft_save": not errors,
        "issues": errors,
        "warnings": warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.json else 2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
