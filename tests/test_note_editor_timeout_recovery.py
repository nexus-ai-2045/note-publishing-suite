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
        "current_url": "https://editor.note.com/notes/example/edit/",
        "evidence_target_url": "https://editor.note.com/notes/example/edit/",
        "operation_id": "heading:mpc-basics:h2",
        "current_route": "chrome_extension",
        "allowed_routes": ["iab", "chrome_extension"],
        "error_code": "cdp_runtime_evaluate_timeout",
        "last_verified_checkpoint": "body_revised_plaintext",
        "completed_operations": ["body:replace:v2"],
        "observed_postconditions": {"body:replace:v2": True},
        "attempts": [],
    }


def test_first_dom_timeout_discards_locator_and_keeps_connected_session():
    state = base_state()
    state["attempts"] = [{
        "route": "chrome_extension", "operation_id": state["operation_id"],
        "result": "failed", "error_code": state["error_code"],
    }]
    result = MODULE.plan_recovery(state)
    assert result["classification"] == "recover_same_route"
    assert result["next_action"] == "reinspect_existing_session_readback"
    assert result["discard"] == ["locator"]
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


def test_dom_timeout_keeps_connected_browser_and_reinspects_existing_tab():
    result = MODULE.plan_recovery(base_state())
    assert result["next_action"] == "reinspect_existing_session_readback"
    assert result["discard"] == ["locator"]


def test_missing_allowed_routes_does_not_authorize_another_browser():
    state = base_state()
    state.pop("allowed_routes")
    state["attempts"] = [
        {"route": state["current_route"], "operation_id": state["operation_id"], "result": "failed"}
        for _ in range(2)
    ]
    result = MODULE.plan_recovery(state)
    assert result["classification"] == "recovery_routes_exhausted"
    assert "selected_route" not in result


def test_uncertain_write_only_allows_readback_without_repeating_input():
    state = base_state()
    state["mutation_attempted"] = True
    state["mutation_result"] = "unknown"
    result = MODULE.plan_recovery(state)
    assert result["next_action"] == "read_only_reconcile_existing_session"
    assert result["mutation_allowed"] is False
    assert state["operation_id"] in result["must_not_repeat"]


def test_changed_target_stops_before_using_old_completion():
    state = base_state()
    state["current_url"] = "https://editor.note.com/notes/another/edit/"
    state["completed_operations"].append(state["operation_id"])
    result = MODULE.plan_recovery(state)
    assert result["classification"] == "target_changed"
    assert result["ok"] is False


def test_transport_disconnect_invalidates_browser_binding():
    state = base_state()
    state["error_code"] = "browser_runtime_disconnected"
    result = MODULE.plan_recovery(state)
    assert "browser_binding" in result["discard"]


def test_malformed_attempts_fail_closed_instead_of_raising():
    state = base_state()
    state["attempts"] = [None]
    assert MODULE.plan_recovery(state)["classification"] == "invalid_recovery_state"


def test_unknown_write_stops_after_readback_route_is_exhausted():
    state = base_state()
    state["mutation_attempted"] = True
    state["attempts"] = [
        {"route": state["current_route"], "operation_id": state["operation_id"], "result": "failed"}
        for _ in range(2)
    ]
    result = MODULE.plan_recovery(state)
    assert result["classification"] == "recovery_readback_exhausted"
    assert result["mutation_allowed"] is False
    assert state["operation_id"] in result["must_not_repeat"]


def test_unknown_route_and_non_object_state_are_rejected():
    state = base_state()
    state["current_route"] = "unregistered_browser"
    assert MODULE.plan_recovery(state)["classification"] == "invalid_recovery_state"
    assert MODULE.plan_recovery(None)["classification"] == "invalid_recovery_state"


def test_missing_current_url_does_not_reuse_completion():
    state = base_state()
    state.pop("current_url")
    state["completed_operations"].append(state["operation_id"])
    assert MODULE.plan_recovery(state)["classification"] == "invalid_recovery_state"


def test_bad_mutation_result_does_not_enable_retry():
    for value in (None, False, "sucess", [], {}):
        state = base_state()
        state["mutation_attempted"] = True
        state["mutation_result"] = value
        assert MODULE.plan_recovery(state)["classification"] == "invalid_recovery_state"


def test_confirmed_completed_mutation_is_not_repeated():
    state = base_state()
    state["mutation_attempted"] = True
    state["mutation_result"] = "completed"
    result = MODULE.plan_recovery(state)
    assert result["classification"] == "already_completed"
    assert result["next_action"] == "skip_mutation_and_readback"
    assert state["operation_id"] in result["must_not_repeat"]


def test_completion_from_another_note_is_not_reused_at_matching_current_url():
    state = base_state()
    state["target_url"] = state["current_url"] = "https://editor.note.com/notes/another/edit/"
    state["completed_operations"].append(state["operation_id"])
    result = MODULE.plan_recovery(state)
    assert result["classification"] == "completion_target_mismatch"
    assert result["ok"] is False


def test_completion_without_its_target_binding_is_rejected():
    state = base_state()
    state.pop("evidence_target_url")
    state["observed_postconditions"][state["operation_id"]] = True
    assert MODULE.plan_recovery(state)["classification"] == "completion_target_mismatch"
