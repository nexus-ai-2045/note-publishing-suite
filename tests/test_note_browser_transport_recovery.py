from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "note_browser_transport_recovery.py"
SPEC = importlib.util.spec_from_file_location("recovery", SCRIPT)
assert SPEC and SPEC.loader
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def row(pid: int, created: str = "2026-08-02T23:17:00") -> dict:
    return {
        "pid": pid,
        "ppid": 46116,
        "name": "node_repl.exe",
        "creation_time": created,
        "parent_present": True,
        "parent_name": "codex.exe",
        "runtime_marker": True,
    }


def operator_assertion(snap: dict, pids: list[int]) -> dict:
    return {
        "schema_version": recovery.OPERATOR_ASSERTION_SCHEMA,
        "operation": recovery.ALLOWED_OPERATION,
        "asserted_by": "operator_current_conversation",
        "target_pids": pids,
        "snapshot_digest": snap["snapshot_digest"],
    }


def test_inspect_classifies_duplicates_without_command_line():
    snap = recovery.snapshot([row(10), row(20)])
    assert snap["ok"] is True
    assert snap["classification"] == "duplicate_node_repl"
    assert all("command_line" not in item for item in snap["processes"])


def test_plan_is_read_only_and_contains_only_exact_target_pids():
    snap = recovery.snapshot([row(10), row(20), row(30)])
    result = recovery.plan_recovery(
        snap,
        operator_assertion(snap, [10, 20]),
        [row(10), row(20), row(30)],
    )
    assert result["ok"] is True
    assert result["classification"] == "recovery_plan_ready"
    assert result["planned_pids"] == [10, 20]
    assert result["execution_performed"] is False
    assert result["approval_verified"] is False
    assert result["runtime_healthy"] == "unknown_until_smoke"


def test_disappeared_approved_processes_are_idempotent_success():
    snap = recovery.snapshot([row(10), row(20)])
    result = recovery.plan_recovery(
        snap,
        operator_assertion(snap, [10, 20]),
        [],
    )
    assert result["classification"] == "already_gone"
    assert result["planned_pids"] == []
    assert result["execution_performed"] is False


def test_pid_reuse_or_identity_change_fails_closed():
    snap = recovery.snapshot([row(10)])
    result = recovery.plan_recovery(
        snap,
        operator_assertion(snap, [10]),
        [row(10, created="2026-08-03T00:00:00")],
    )
    assert result["classification"] == "target_identity_changed"
    assert result["execution_performed"] is False


def test_stale_or_wrong_operator_assertion_is_rejected():
    snap = recovery.snapshot([row(10)])
    bad = operator_assertion(snap, [10])
    bad["snapshot_digest"] = "wrong"
    result = recovery.plan_recovery(snap, bad, [row(10)])
    assert result["classification"] == "operator_assertion_rejected"
    assert result["execution_performed"] is False


def test_codex_chrome_and_generic_node_are_never_allowed():
    unsafe = row(10)
    unsafe["name"] = "node.exe"
    snap = recovery.snapshot([unsafe])
    result = recovery.plan_recovery(snap, operator_assertion(snap, [10]), [unsafe])
    assert result["classification"] == "unsafe_target_rejected"
    assert result["execution_performed"] is False


def test_boolean_pid_is_rejected():
    snap = recovery.snapshot([row(10)])
    bad = operator_assertion(snap, [10])
    bad["target_pids"] = [True]

    result = recovery.plan_recovery(snap, bad, [row(10)])

    assert result["classification"] == "operator_assertion_rejected"
    assert "target_pids_invalid" in result["errors"]


def test_unhashable_non_integer_pid_is_rejected_without_exception():
    snap = recovery.snapshot([row(10)])
    bad = operator_assertion(snap, [10])
    bad["target_pids"] = [{"pid": 10}]

    result = recovery.plan_recovery(snap, bad, [row(10)])

    assert result["classification"] == "operator_assertion_rejected"
    assert "target_pids_invalid" in result["errors"]


def test_public_recovery_module_has_no_process_termination_command():
    source = SCRIPT.read_text(encoding="utf-8")
    package = (SCRIPT.parents[1] / "package.yaml").read_text(encoding="utf-8")

    assert "Stop-Process" not in source
    assert "terminate_exact" not in source
    assert "mode: read_only_plan" in package
    assert "process_termination_performed: false" in package


def test_malformed_snapshot_fails_closed():
    snap = recovery.snapshot([row(10)])
    snap["processes"] = [{"pid": 10}]

    result = recovery.plan_recovery(snap, operator_assertion(snap, [10]), [row(10)])

    assert result["classification"] == "invalid_snapshot"
    assert result["execution_performed"] is False


def test_duplicate_snapshot_pid_fails_closed():
    snap = recovery.snapshot([row(10), row(20)])
    snap["processes"] = [row(10), row(10)]

    result = recovery.plan_recovery(snap, operator_assertion(snap, [10]), [row(10)])

    assert result["classification"] == "invalid_snapshot"
    assert "snapshot_process_pid_duplicate" in result["errors"]


def test_non_object_snapshot_fails_closed():
    result = recovery.plan_recovery([], {}, [])

    assert result["classification"] == "invalid_snapshot"
    assert result["errors"] == ["snapshot_not_object"]
    assert result["execution_performed"] is False
