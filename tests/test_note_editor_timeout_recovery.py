from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "note_editor_timeout_recovery.py"
SPEC = importlib.util.spec_from_file_location("note_editor_timeout_recovery", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def base_state() -> dict:
    return {
        "target_url": "https://editor.note.com/notes/example/edit/",
        "operation_id": "heading:mpc-basics:h2",
        "current_route": "chrome_extension",
        "allowed_routes": ["iab", "chrome_extension"],
        "error_code": "cdp_runtime_evaluate_timeout",
        "last_verified_checkpoint": "body_revised_plaintext",
        "completed_operations": ["body:replace:v2"],
        "observed_postconditions": {"body:replace:v2": True},
        "attempts": [],
    }


def test_first_timeout_discards_stale_bindings_and_reclaims_exact_tab():
    state = base_state()
    state["attempts"] = [{
        "route": "chrome_extension", "operation_id": state["operation_id"],
        "result": "failed", "error_code": state["error_code"],
    }]
    result = MODULE.plan_recovery(state)
    assert result["classification"] == "recover_same_route"
    assert result["next_action"] == "new_session_reinventory_reclaim_readback"
    assert "browser_binding" in result["discard"]
    assert "body:replace:v2" in result["must_not_repeat"]


def test_second_same_route_timeout_closes_route_and_switches():
    state = base_state()
    state["attempts"] = [
        {"route": "chrome_extension", "operation_id": state["operation_id"], "result": "failed"},
        {"route": "chrome_extension", "operation_id": state["operation_id"], "result": "failed"},
    ]
    result = MODULE.plan_recovery(state)
    assert result["classification"] == "same_route_closed"
    assert result["closed_route"] == "chrome_extension"
    assert result["selected_route"] == "iab"


def test_completed_operation_is_never_repeated_after_timeout():
    state = base_state()
    state["operation_id"] = "body:replace:v2"
    result = MODULE.plan_recovery(state)
    assert result["classification"] == "already_completed"
    assert result["next_action"] == "skip_mutation_and_readback"


def test_exhausted_routes_fail_closed_at_human_boundary():
    state = base_state()
    state["attempts"] = [
        {"route": route, "operation_id": state["operation_id"], "result": "failed"}
        for route in ("iab", "iab", "chrome_extension", "chrome_extension")
    ]
    result = MODULE.plan_recovery(state)
    assert result["ok"] is False
    assert result["classification"] == "recovery_routes_exhausted"
    assert result["next_action"] == "human_or_runtime_restart_boundary"


def test_unknown_error_is_not_guessed():
    state = base_state()
    state["error_code"] = "mystery_error"
    result = MODULE.plan_recovery(state)
    assert result["ok"] is False
    assert result["classification"] == "unknown_browser_runtime_error"
