#!/usr/bin/env python3
"""Validate a Note editor pre-publication observation snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FOOTER_KEYS = ("footer_embeds", "footer_embed_urls", "footer")
TOP_IMAGE_KEYS = ("top_image", "image_upload")


def normalize_tag(tag: Any) -> str:
    return str(tag).strip().lstrip("#").casefold()


def issue(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def manual_boundary_for(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    boundaries = as_dict(data.get("manual_boundaries"))
    for key in keys:
        value = boundaries.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def validate_top_image(data: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    boundaries: list[dict[str, str]] = []
    top_image = as_dict(data.get("top_image"))
    if top_image.get("present") is True:
        return issues, boundaries

    boundary = manual_boundary_for(data, TOP_IMAGE_KEYS)
    if boundary:
        boundaries.append(
            {
                "code": "top_image_manual_boundary",
                "message": boundary,
            }
        )
        return issues, boundaries

    issues.append(
        issue(
            "error",
            "top_image_missing",
            "top image is not observed and no manual upload boundary is recorded",
        )
    )
    return issues, boundaries


def validate_toc(data: dict[str, Any]) -> list[dict[str, str]]:
    toc_count = data.get("toc_count")
    if isinstance(toc_count, int) and toc_count >= 1:
        return []
    return [
        issue(
            "error",
            "toc_missing",
            "table of contents is not observed",
        )
    ]


def validate_footer(data: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    boundaries: list[dict[str, str]] = []
    footer = as_dict(data.get("footer"))
    required_urls = [str(url) for url in as_list(footer.get("required_urls"))]
    figures = {str(url) for url in as_list(footer.get("figures"))}
    cards = {str(url) for url in as_list(footer.get("cards"))}
    raw_counts = as_dict(footer.get("raw_counts"))
    boundary = manual_boundary_for(data, FOOTER_KEYS)

    for url in required_urls:
        raw_count = raw_counts.get(url, 0)
        try:
            raw_count = int(raw_count)
        except (TypeError, ValueError):
            raw_count = 0
        cardized = url in figures or url in cards
        if cardized and raw_count == 0:
            continue
        if boundary:
            boundaries.append(
                {
                    "code": "footer_embed_manual_boundary",
                    "message": f"{url}: {boundary}",
                }
            )
            continue
        if raw_count > 0:
            issues.append(
                issue(
                    "error",
                    "footer_raw_url",
                    f"footer URL remains raw without a manual boundary: {url}",
                )
            )
        else:
            issues.append(
                issue(
                    "error",
                    "footer_embed_missing",
                    f"footer URL is not observed as a card/embed: {url}",
                )
            )
    return issues, boundaries


def validate_magazine(data: dict[str, Any]) -> list[dict[str, str]]:
    magazine = as_dict(data.get("magazine"))
    if magazine.get("added") is True:
        return []
    return [
        issue(
            "error",
            "magazine_missing",
            "target magazine is not observed as added",
        )
    ]


def validate_tags(data: dict[str, Any]) -> list[dict[str, str]]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for tag in as_list(data.get("tags")):
        normalized = normalize_tag(tag)
        if not normalized:
            continue
        if normalized in seen:
            duplicates.add(normalized)
        seen.add(normalized)
    if not duplicates:
        return []
    return [
        issue(
            "error",
            "duplicate_tags",
            "duplicate tags observed: " + ", ".join(sorted(duplicates)),
        )
    ]


def validate_article_type(data: dict[str, Any]) -> list[dict[str, str]]:
    article_type = data.get("article_type")
    if isinstance(article_type, str) and article_type.strip():
        return []
    return [
        issue(
            "error",
            "article_type_missing",
            "free/paid article type is not recorded",
        )
    ]


def validate_final_buttons(data: dict[str, Any]) -> list[dict[str, str]]:
    buttons = as_list(data.get("final_buttons"))
    if not buttons:
        return [
            issue(
                "error",
                "final_button_state_missing",
                "final publication button state is not recorded",
            )
        ]

    issues: list[dict[str, str]] = []
    for button in buttons:
        item = as_dict(button)
        if item.get("clicked") is True:
            label = item.get("label") or "unknown"
            issues.append(
                issue(
                    "error",
                    "final_button_clicked",
                    f"final publication button was clicked: {label}",
                )
            )
    return issues


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    manual_boundaries: list[dict[str, str]] = []

    top_issues, top_boundaries = validate_top_image(data)
    footer_issues, footer_boundaries = validate_footer(data)
    issues.extend(top_issues)
    issues.extend(validate_toc(data))
    issues.extend(footer_issues)
    issues.extend(validate_magazine(data))
    issues.extend(validate_tags(data))
    issues.extend(validate_article_type(data))
    issues.extend(validate_final_buttons(data))
    manual_boundaries.extend(top_boundaries)
    manual_boundaries.extend(footer_boundaries)

    hard_errors = [item for item in issues if item["severity"] == "error"]
    return {
        "ok": not hard_errors,
        "ready_for_publish": not hard_errors and not manual_boundaries,
        "issues": issues,
        "manual_boundaries": manual_boundaries,
        "external_actions_performed": [],
        "publication_actions_performed": [],
    }


def load_observation(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("observation root must be an object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Note editor pre-publication observation snapshot."
    )
    parser.add_argument("observation", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = build_result(load_observation(args.observation))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        ready = "true" if result["ready_for_publish"] else "false"
        print(f"OK ready_for_publish={ready}")
        for boundary in result["manual_boundaries"]:
            print(f"manual_boundary:{boundary['code']} {boundary['message']}")
    else:
        print("NG")
        for item in result["issues"]:
            print(f"{item['severity']}:{item['code']} {item['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
