#!/usr/bin/env python3
"""note image upload automation boundary guarantee tests."""

from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_checker_module():
    spec = importlib.util.spec_from_file_location(
        "note_image_upload_boundary_check",
        ROOT / "scripts/note_image_upload_boundary_check.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_policy() -> dict:
    return json.loads(
        (ROOT / "data/note_image_upload_automation_policy.json").read_text(
            encoding="utf-8"
        )
    )


def test_policy_separates_allowed_confirmation_and_blocked_routes():
    policy = load_policy()
    routes = {route["route_id"]: route for route in policy["automation_routes"]}

    assert routes["manual_user_upload"]["status"] == "allowed_now"
    assert routes["visible_windows_file_dialog"]["status"] == "requires_user_confirmation"
    assert routes["cmux_dom_file_paste"]["status"] == "requires_user_confirmation"
    assert routes["chrome_api_cookie_hidden_os"]["status"] == "blocked"

    assert routes["visible_windows_file_dialog"]["requires_current_conversation_approval"] is True
    assert routes["cmux_dom_file_paste"]["requires_current_conversation_approval"] is True
    assert routes["chrome_api_cookie_hidden_os"]["requires_current_conversation_approval"] is False


def test_policy_blocks_publication_and_session_surfaces():
    policy = load_policy()

    for action in [
        "chrome_real_browser",
        "note_api",
        "cookie_read",
        "session_read",
        "hidden_window_operation",
        "os_focus_steal",
        "publish",
        "schedule_publish",
        "external_share",
    ]:
        assert action in policy["prohibited_actions"]

    assert policy["public_action_allowed"] is False
    assert policy["internal_browser_image_upload_fully_automated"] is False


def test_policy_has_windows_and_mac_environment_matrix():
    policy = load_policy()
    matrix = {item["os_family"]: item for item in policy["environment_matrix"]}

    assert matrix["windows"]["minimum_os"] == "Windows 10"
    assert matrix["windows"]["recommended_browsers"] == [
        "Google Chrome",
        "Microsoft Edge",
        "Mozilla Firefox",
    ]
    assert matrix["mac"]["minimum_os"] == "macOS 14"
    assert matrix["mac"]["recommended_browsers"] == [
        "Safari",
        "Google Chrome",
    ]

    for item in matrix.values():
        assert item["guarantee"] == "stopline_and_boundary"
        assert item["actual_upload_success_guaranteed"] is False
        assert "attach_or_visible_dialog_unavailable" in item["stoplines"]
        assert "note_official_recommended_environment" in item["sources"]


def test_boundary_docs_and_package_reference_the_guarantee():
    docs = {
        "parent": (ROOT / "SKILL.md").read_text(encoding="utf-8"),
        "readme": (ROOT / "README.md").read_text(encoding="utf-8"),
        "editor": (ROOT / "skills/note-editor-prepublish/SKILL.md").read_text(
            encoding="utf-8"
        ),
        "ops": (ROOT / "skills/note-editor-ops/SKILL.md").read_text(
            encoding="utf-8"
        ),
        "boundary": (
            ROOT / "references/note-image-upload-automation-boundary.md"
        ).read_text(encoding="utf-8"),
        "package": (ROOT / "package.yaml").read_text(encoding="utf-8"),
    }

    for name, text in docs.items():
        assert "note-image-upload-automation-boundary" in text, name
        assert "note_image_upload_boundary_check.py" in text, name

    assert "画面に見えている Windows ファイル選択ダイアログ" in docs["boundary"]
    assert "Chrome、note API、Cookie、セッション読み取り" in docs["boundary"]
    assert "Windows / Mac 環境差" in docs["boundary"]
    assert "残務ゼロ" in docs["boundary"]
    assert "cmux_dom_file_paste" in docs["boundary"]
    assert "browser-scoped `File` paste" in docs["boundary"]


def test_guarantee_checker_returns_residual_work_zero():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/note_image_upload_boundary_check.py"),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["residual_work_zero"] is True
    assert payload["external_actions_performed"] == []
    assert payload["stop_causes"] == []


def test_cmux_route_contract_drift_fails_closed():
    checker = load_checker_module()
    policy = load_policy()

    unsafe_mutations = {
        "boundary": "hidden_dom_any_target",
        "smoke_checks": ["placeholder"],
        "rollback": "continue_and_save",
        "summary": "OS clipboard injection を使う",
    }
    for key, value in unsafe_mutations.items():
        candidate = deepcopy(policy)
        route = next(
            item
            for item in candidate["automation_routes"]
            if item["route_id"] == "cmux_dom_file_paste"
        )
        route[key] = value
        errors = checker.validate_policy(candidate)
        assert any(f"cmux_dom_file_paste.{key}" in error for error in errors)


def test_confirmation_route_registry_drift_fails_closed():
    checker = load_checker_module()
    policy = load_policy()
    policy["human_confirmation_before_expansion"].remove("cmux_dom_file_paste")

    errors = checker.validate_policy(policy)
    assert any("human_confirmation_before_expansion missing" in error for error in errors)


def test_cmux_route_requires_visible_active_target_editor():
    checker = load_checker_module()
    policy = load_policy()
    route = next(
        item
        for item in policy["automation_routes"]
        if item["route_id"] == "cmux_dom_file_paste"
    )
    route["smoke_checks"] = [
        check
        for check in route["smoke_checks"]
        if check != "target_editor_visible_active_and_matches"
    ]

    errors = checker.validate_policy(policy)
    assert any("cmux_dom_file_paste.smoke_checks" in error for error in errors)


def test_unknown_automation_route_fails_closed():
    checker = load_checker_module()
    policy = load_policy()
    policy["automation_routes"].append(
        {
            "route_id": "hidden_dom_upload",
            "boundary": "hidden_dom",
            "status": "allowed_now",
            "requires_current_conversation_approval": False,
            "summary": "unsafe route",
            "smoke_checks": ["placeholder"],
            "rollback": "continue_and_save",
        }
    )

    errors = checker.validate_policy(policy)
    assert any("automation_routes unexpected" in error for error in errors)


def test_duplicate_automation_route_id_fails_closed():
    checker = load_checker_module()
    policy = load_policy()
    cmux_route = next(
        item
        for item in policy["automation_routes"]
        if item["route_id"] == "cmux_dom_file_paste"
    )
    policy["automation_routes"].insert(0, deepcopy(cmux_route))

    errors = checker.validate_policy(policy)
    assert any("automation_routes duplicate route_id" in error for error in errors)
