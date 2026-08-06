#!/usr/bin/env python3
"""Validate Note cover image upload route measurements."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FIXTURE_SCHEMA = "note_cover_image_upload_measurement.v1"
PRODUCTION_SCHEMA = "note_cover_image_upload_production_record.v1"
ALLOWED_SCHEMAS = (FIXTURE_SCHEMA, PRODUCTION_SCHEMA)
FIXTURE_SCOPE_MARKERS = ("fixture", "non-public", "editor_fixture")
PRODUCTION_SCOPE_MARKERS = ("production candidate", "non-public production candidate")
PUBLICATION_KEYS = ("publication_actions_performed", "public_actions_performed")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def issue(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


def routes_by_surface(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    routes: dict[str, dict[str, Any]] = {}
    for route in as_list(data.get("routes")):
        item = as_dict(route)
        surface = text(item.get("surface")).casefold()
        if surface:
            routes[surface] = item
    if not routes and text(data.get("surface")):
        routes[text(data.get("surface")).casefold()] = data
    return routes


def validate(data: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []

    schema = data.get("schema")
    if schema not in ALLOWED_SCHEMAS:
        issues.append(
            issue(
                "error",
                "schema_mismatch",
                f"schema must be one of: {', '.join(ALLOWED_SCHEMAS)}",
            )
        )

    source_scope = text(data.get("source_scope")).casefold()
    is_fixture_schema = schema == FIXTURE_SCHEMA
    is_production_schema = schema == PRODUCTION_SCHEMA
    allowed_scope_markers = (
        FIXTURE_SCOPE_MARKERS if is_fixture_schema else PRODUCTION_SCOPE_MARKERS
    )
    if schema in ALLOWED_SCHEMAS and not any(
        marker in source_scope for marker in allowed_scope_markers
    ):
        issues.append(
            issue(
                "error",
                "scope_not_allowed",
                "cover image upload record must be a non-public fixture or non-public production candidate draft",
            )
        )

    for key in PUBLICATION_KEYS:
        actions = as_list(data.get(key))
        if actions:
            issues.append(
                issue(
                    "error",
                    "publication_action_recorded",
                    f"{key} must be empty for cover image upload measurement",
                )
            )

    image_source = as_dict(data.get("image_source"))
    for key in ("path", "width", "height", "bytes"):
        if not image_source.get(key):
            issues.append(
                issue("error", "image_source_incomplete", f"image_source.{key} is required")
            )

    routes = routes_by_surface(data)
    iab = next(
        (route for surface, route in routes.items() if "in-app" in surface),
        {},
    )
    chrome = next(
        (route for surface, route in routes.items() if "chrome" in surface),
        {},
    )

    if is_fixture_schema and not iab:
        issues.append(issue("error", "in_app_route_missing", "in-app Browser route is required"))
    elif iab and text(iab.get("status")) != "blocked":
        issues.append(
            issue(
                "error",
                "in_app_route_not_blocked",
                "in-app Browser cover upload route must be recorded as blocked unless a real file set route is proven",
            )
        )

    if not chrome:
        issues.append(issue("error", "chrome_route_missing", "ChromeCodex route is required"))
    elif text(chrome.get("status")) != "passed":
        issues.append(
            issue("error", "chrome_route_not_passed", "ChromeCodex cover upload route must pass")
        )
    else:
        observations = as_dict(chrome.get("observations"))
        required_chrome_signals = [
            "existing_chrome_tabs_listed_before_claim",
            "filechooser_event_observed",
            "set_files_succeeded",
            "crop_modal_observed",
            "crop_save_clicked",
            "image_visible_after_delay",
            "draft_saved_notice_observed",
        ]
        if is_production_schema:
            required_chrome_signals[0] = "existing_chrome_tabs_listed_before_operation"
            required_chrome_signals.extend(
                [
                    "target_editor_url_confirmed",
                    "target_title_confirmed",
                    "draft_save_clicked",
                    "post_save_publish_proceed_visible",
                ]
            )

        for key in required_chrome_signals:
            if observations.get(key) is not True:
                issues.append(
                    issue("error", "chrome_success_signal_missing", f"{key} must be true")
                )

        if is_production_schema:
            for key in ("pre_upload_post_button_visible", "post_save_post_button_visible"):
                if observations.get(key) is True:
                    issues.append(
                        issue("error", "public_button_state_unsafe", f"{key} must not be true")
                    )

        uploaded = as_dict(chrome.get("uploaded_image"))
        if uploaded.get("alt") != "eyecatch":
            issues.append(issue("error", "eyecatch_missing", "uploaded image alt must be eyecatch"))
        if uploaded.get("natural_width") != 1280 or uploaded.get("natural_height") != 670:
            issues.append(
                issue(
                    "error",
                    "uploaded_dimensions_unexpected",
                    "uploaded cover image should be cropped to 1280x670 in Note",
                )
            )

    hard_errors = [item for item in issues if item["severity"] == "error"]
    return {
        "ok": not hard_errors,
        "routes": {
            "in_app_browser": text(iab.get("status")) if iab else "missing",
            "chrome_codex": text(chrome.get("status")) if chrome else "missing",
        },
        "issues": issues,
        "publication_actions_performed": as_list(data.get("publication_actions_performed")),
        "public_actions_performed": as_list(data.get("public_actions_performed")),
        "external_actions_performed": as_list(data.get("external_actions_performed")),
        "guarantee_scope": (
            "cover_image_fixture_measurement_only_no_publish_or_public_share"
            if is_fixture_schema
            else "cover_image_production_candidate_draft_save_only_no_publish_or_public_share"
        ),
    }


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("measurement root must be an object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Note cover image upload route measurement."
    )
    parser.add_argument("measurement", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = validate(load(args.measurement))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print("OK cover image upload measurement")
    else:
        print("NG")
        for item in result["issues"]:
            print(f"{item['severity']}:{item['code']} {item['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
