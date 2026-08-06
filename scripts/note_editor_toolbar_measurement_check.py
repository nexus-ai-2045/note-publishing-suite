#!/usr/bin/env python3
"""Validate Note editor toolbar variant measurement snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_SCHEMA = "note_editor_toolbar_variant_measurement.v1"
FIXTURE_SCOPE_MARKERS = ("fixture", "non-public", "editor_fixture")
PUBLICATION_KEYS = (
    "publication_actions_performed",
    "external_actions_performed",
    "public_actions_performed",
)
DEFAULT_REQUIRED_OBSERVED_VARIANTS = ("footer_toolbar", "side_like_toolbar")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def issue(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


def button_label(button: Any) -> str:
    item = as_dict(button)
    return text(item.get("label") or item.get("ariaLabel") or item.get("aria-label"))


def classify_variants(data: dict[str, Any]) -> list[str]:
    observed: set[str] = set()
    for variant in as_list(data.get("variants")):
        state = as_dict(as_dict(variant).get("state"))
        buttons = as_list(state.get("buttons"))
        labels = {button_label(button) for button in buttons}

        if any(as_dict(button).get("nearBottom") is True for button in buttons):
            if {"メニューを開く", "リンク"} & labels:
                observed.add("footer_toolbar")

        side_labels = {"目次", "noteのヒント", "エディタのガイド"}
        if side_labels & labels:
            observed.add("side_like_toolbar")

        selection = as_dict(state.get("selection"))
        if text(selection.get("text")):
            observed.add("selection_toolbar_signal")

        label = text(as_dict(variant).get("label")).casefold()
        if "right_click" in label or "context" in label:
            if any(label in labels for label in ("コピー", "貼り付け", "切り取り")):
                observed.add("context_menu_signal")
    return sorted(observed)


def validate(data: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []

    if data.get("schema") != REQUIRED_SCHEMA:
        issues.append(
            issue(
                "error",
                "schema_mismatch",
                f"schema must be {REQUIRED_SCHEMA}",
            )
        )

    source_scope = text(data.get("source_scope")).casefold()
    if not any(marker in source_scope for marker in FIXTURE_SCOPE_MARKERS):
        issues.append(
            issue(
                "error",
                "not_fixture_scope",
                "toolbar measurement must run against a non-public fixture/editor_fixture draft",
            )
        )

    for key in PUBLICATION_KEYS:
        actions = as_list(data.get(key))
        if actions:
            issues.append(
                issue(
                    "error",
                    "publication_action_recorded",
                    f"{key} must be empty for toolbar measurement",
                )
            )

    variants = as_list(data.get("variants"))
    if not variants:
        issues.append(issue("error", "variants_missing", "variants must be non-empty"))

    for index, variant in enumerate(variants):
        state = as_dict(as_dict(variant).get("state"))
        viewport = as_dict(state.get("viewport"))
        buttons = as_list(state.get("buttons"))
        if not viewport.get("width") or not viewport.get("height"):
            issues.append(
                issue(
                    "error",
                    "viewport_missing",
                    f"variant {index} does not record viewport width/height",
                )
            )
        if not buttons:
            issues.append(
                issue(
                    "error",
                    "buttons_missing",
                    f"variant {index} does not record toolbar/button candidates",
                )
            )

    required_variants = [
        text(item)
        for item in as_list(data.get("required_observed_variants"))
        if text(item)
    ] or list(DEFAULT_REQUIRED_OBSERVED_VARIANTS)
    observed_variants = classify_variants(data)
    for required in required_variants:
        if required in observed_variants:
            continue
        issues.append(
            issue(
                "error",
                f"{required}_not_observed",
                f"required toolbar variant was not observed: {required}",
            )
        )

    stop_causes = [text(item) for item in as_list(data.get("stop_causes")) if text(item)]
    hard_errors = [item for item in issues if item["severity"] == "error"]
    return {
        "ok": not hard_errors,
        "coverage_complete": not hard_errors and not stop_causes,
        "observed_variants": observed_variants,
        "required_observed_variants": required_variants,
        "unverified_variants": stop_causes,
        "issues": issues,
        "publication_actions_performed": as_list(data.get("publication_actions_performed")),
        "external_actions_performed": as_list(data.get("external_actions_performed")),
        "guarantee_scope": "toolbar_measurement_snapshot_only_no_publish_or_external_action",
    }


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("measurement root must be an object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Note editor toolbar variant measurement snapshot."
    )
    parser.add_argument("measurement", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = validate(load(args.measurement))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print(f"OK coverage_complete={str(result['coverage_complete']).lower()}")
    else:
        print("NG")
        for item in result["issues"]:
            print(f"{item['severity']}:{item['code']} {item['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
