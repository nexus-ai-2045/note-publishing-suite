#!/usr/bin/env python3
"""Validate the note image upload automation boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "data/note_image_upload_automation_policy.json"
BOUNDARY_PATH = ROOT / "references/note-image-upload-automation-boundary.md"

REQUIRED_ROUTES: dict[str, dict[str, Any]] = {
    "manual_user_upload": {
        "status": "allowed_now",
        "requires_current_conversation_approval": True,
    },
    "visible_windows_file_dialog": {
        "status": "requires_user_confirmation",
        "requires_current_conversation_approval": True,
    },
    "chrome_api_cookie_hidden_os": {
        "status": "blocked",
        "requires_current_conversation_approval": False,
    },
}

REQUIRED_PROHIBITIONS = {
    "chrome_real_browser",
    "chrome_devtools_protocol",
    "note_api",
    "cookie_read",
    "session_read",
    "token_read",
    "hidden_window_operation",
    "offscreen_monitor_operation",
    "os_focus_steal",
    "keystroke_injection",
    "clipboard_injection",
    "publish",
    "schedule_publish",
    "external_share",
}

REQUIRED_ENVIRONMENTS: dict[str, dict[str, Any]] = {
    "windows": {
        "minimum_os": "Windows 10",
        "recommended_browsers": [
            "Google Chrome",
            "Microsoft Edge",
            "Mozilla Firefox",
        ],
    },
    "mac": {
        "minimum_os": "macOS 14",
        "recommended_browsers": [
            "Safari",
            "Google Chrome",
        ],
    },
}

REQUIRED_DOCS = {
    "SKILL.md": ["note-image-upload-automation-boundary", "note_image_upload_boundary_check.py"],
    "README.md": ["note-image-upload-automation-boundary", "note_image_upload_boundary_check.py"],
    "skills/note-editor-prepublish/SKILL.md": [
        "note-image-upload-automation-boundary",
        "note_image_upload_boundary_check.py",
    ],
    "skills/note-editor-ops/SKILL.md": [
        "note-image-upload-automation-boundary",
        "note_image_upload_boundary_check.py",
    ],
    "package.yaml": ["note_image_upload_boundary_check.py"],
}


def load_policy() -> dict[str, Any]:
    with POLICY_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("policy root must be an object")
    return data


def validate_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if policy.get("public_action_allowed") is not False:
        errors.append("public_action_allowed must be false")
    if policy.get("internal_browser_image_upload_fully_automated") is not False:
        errors.append("internal_browser_image_upload_fully_automated must be false")

    environments = policy.get("environment_matrix")
    if not isinstance(environments, list) or not environments:
        errors.append("environment_matrix must be a non-empty list")
    else:
        environments_by_os = {
            item.get("os_family"): item
            for item in environments
            if isinstance(item, dict) and isinstance(item.get("os_family"), str)
        }
        missing_environments = set(REQUIRED_ENVIRONMENTS) - set(environments_by_os)
        if missing_environments:
            errors.append(
                "environment_matrix missing: " + ", ".join(sorted(missing_environments))
            )
        for os_family, expected in REQUIRED_ENVIRONMENTS.items():
            item = environments_by_os.get(os_family)
            if not item:
                continue
            for key, value in expected.items():
                if item.get(key) != value:
                    errors.append(f"environment_matrix.{os_family}.{key} must match official recommendation")
            if item.get("guarantee") != "stopline_and_boundary":
                errors.append(f"environment_matrix.{os_family}.guarantee must be stopline_and_boundary")
            if item.get("actual_upload_success_guaranteed") is not False:
                errors.append(f"environment_matrix.{os_family}.actual_upload_success_guaranteed must be false")
            stoplines = set(item.get("stoplines") or [])
            if "attach_or_visible_dialog_unavailable" not in stoplines:
                errors.append(f"environment_matrix.{os_family}.stoplines missing attach_or_visible_dialog_unavailable")
            sources = set(item.get("sources") or [])
            if "note_official_recommended_environment" not in sources:
                errors.append(f"environment_matrix.{os_family}.sources missing note_official_recommended_environment")

    routes = policy.get("automation_routes")
    if not isinstance(routes, list) or not routes:
        errors.append("automation_routes must be a non-empty list")
        return errors

    routes_by_id = {
        route.get("route_id"): route
        for route in routes
        if isinstance(route, dict) and isinstance(route.get("route_id"), str)
    }
    missing_routes = set(REQUIRED_ROUTES) - set(routes_by_id)
    if missing_routes:
        errors.append("automation_routes missing: " + ", ".join(sorted(missing_routes)))

    for route_id, expected in REQUIRED_ROUTES.items():
        route = routes_by_id.get(route_id)
        if not route:
            continue
        for key, value in expected.items():
            actual = route.get(key)
            if actual is not value if isinstance(value, bool) else actual != value:
                label = str(value).lower() if isinstance(value, bool) else value
                errors.append(f"automation_routes.{route_id}.{key} must be {label}")
        if route.get("status") != "blocked":
            if not route.get("smoke_checks"):
                errors.append(f"automation_routes.{route_id}.smoke_checks must be non-empty")
            if not route.get("rollback"):
                errors.append(f"automation_routes.{route_id}.rollback must be non-empty")

    prohibitions = set(policy.get("prohibited_actions") or [])
    missing_prohibitions = REQUIRED_PROHIBITIONS - prohibitions
    if missing_prohibitions:
        errors.append("prohibited_actions missing: " + ", ".join(sorted(missing_prohibitions)))

    return errors


def validate_docs() -> list[str]:
    errors: list[str] = []
    if not BOUNDARY_PATH.exists():
        errors.append(f"missing {BOUNDARY_PATH.relative_to(ROOT)}")
    else:
        boundary = BOUNDARY_PATH.read_text(encoding="utf-8")
        for needle in [
            "画面に見えている Windows ファイル選択ダイアログ",
            "Chrome、note API、Cookie、セッション読み取り",
            "Windows / Mac 環境差",
            "残務ゼロ",
        ]:
            if needle not in boundary:
                errors.append(f"boundary missing: {needle}")

    for raw_path, needles in REQUIRED_DOCS.items():
        path = ROOT / raw_path
        if not path.exists():
            errors.append(f"missing {raw_path}")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                errors.append(f"{raw_path} missing: {needle}")

    return errors


def build_result() -> dict[str, Any]:
    stop_causes: list[str] = []
    policy = load_policy()
    stop_causes.extend(validate_policy(policy))
    stop_causes.extend(validate_docs())

    return {
        "ok": not stop_causes,
        "residual_work_zero": not stop_causes,
        "policy": str(POLICY_PATH.relative_to(ROOT)),
        "boundary": str(BOUNDARY_PATH.relative_to(ROOT)),
        "external_actions_performed": [],
        "stop_causes": stop_causes,
        "guarantee_scope": "boundary_only_no_actual_upload_or_publication",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate note image upload boundary.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = build_result()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print("OK residual_work_zero=true")
    else:
        print("NG")
        for cause in result["stop_causes"]:
            print(f"- {cause}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
