#!/usr/bin/env python3
"""Read-only recovery planning for duplicated/stale browser transports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "note-browser-transport-recovery/v1"
OPERATOR_ASSERTION_SCHEMA = "note-browser-process-operator-assertion/v1"
ALLOWED_NAMES = {"node_repl.exe"}
ALLOWED_OPERATION = "plan_exact_browser_transport_process_recovery"


def _powershell_json(script: str) -> Any:
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "powershell_failed")
    raw = completed.stdout.strip()
    return [] if not raw else json.loads(raw)


def inventory() -> list[dict[str, Any]]:
    rows = _powershell_json(
        r"""
$all = Get-CimInstance Win32_Process
$rows = foreach ($p in $all | Where-Object Name -eq 'node_repl.exe') {
  $parent = $all | Where-Object ProcessId -eq $p.ParentProcessId
  [pscustomobject]@{
    pid = [int]$p.ProcessId
    ppid = [int]$p.ParentProcessId
    name = $p.Name
    creation_time = [string]$p.CreationDate
    parent_present = [bool]$parent
    parent_name = if ($parent) { [string]$parent.Name } else { $null }
    runtime_marker = [bool]($p.CommandLine -match '\\OpenAI\\Codex\\runtimes\\cua_node\\.+\\bin\\node_repl\.exe')
  }
}
$rows | ConvertTo-Json -Depth 4 -Compress
"""
    )
    if isinstance(rows, dict):
        rows = [rows]
    return sorted(rows, key=lambda row: int(row["pid"]))


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "pid": int(row["pid"]),
        "ppid": int(row["ppid"]),
        "name": str(row["name"]),
        "creation_time": str(row["creation_time"]),
        "parent_present": bool(row["parent_present"]),
        "parent_name": row.get("parent_name"),
        "runtime_marker": bool(row["runtime_marker"]),
    }


def snapshot(rows: list[dict[str, Any]]) -> dict[str, Any]:
    identities = [_identity(row) for row in rows]
    canonical = json.dumps(identities, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": SCHEMA,
        "ok": True,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only",
        "processes": identities,
        "snapshot_digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "classification": "duplicate_node_repl" if len(identities) > 1 else (
            "single_node_repl" if identities else "no_node_repl"
        ),
        "stopline": "This script never terminates processes; a trusted runtime must verify human approval before external execution.",
    }


def validate_snapshot(snap: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(snap, dict):
        return [], ["snapshot_not_object"]
    if snap.get("schema_version") != SCHEMA:
        return [], ["invalid_snapshot_schema"]
    rows = snap.get("processes")
    if not isinstance(rows, list):
        return [], ["snapshot_processes_not_list"]

    identities: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            return [], ["snapshot_process_not_object"]
        try:
            identities.append(_identity(row))
        except (KeyError, TypeError, ValueError):
            return [], ["snapshot_process_identity_invalid"]
    pids = [row["pid"] for row in identities]
    if len(pids) != len(set(pids)):
        return [], ["snapshot_process_pid_duplicate"]

    canonical = json.dumps(identities, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if snap.get("snapshot_digest") != digest:
        return [], ["snapshot_digest_invalid"]
    return identities, []


def validate_operator_assertion(assertion: dict[str, Any], snap: dict[str, Any]) -> list[str]:
    identities, errors = validate_snapshot(snap)
    if not isinstance(assertion, dict):
        return [*errors, "operator_assertion_not_object"]
    if assertion.get("schema_version") != OPERATOR_ASSERTION_SCHEMA:
        errors.append("invalid_operator_assertion_schema")
    if assertion.get("operation") != ALLOWED_OPERATION:
        errors.append("invalid_operation")
    if assertion.get("asserted_by") != "operator_current_conversation":
        errors.append("missing_operator_assertion")
    if assertion.get("snapshot_digest") != snap.get("snapshot_digest"):
        errors.append("snapshot_digest_mismatch")
    pids = assertion.get("target_pids")
    valid_pids = (
        isinstance(pids, list)
        and bool(pids)
        and all(isinstance(pid, int) and not isinstance(pid, bool) for pid in pids)
    )
    if not valid_pids:
        errors.append("target_pids_invalid")
    elif len(pids) != len(set(pids)):
        errors.append("target_pids_duplicate")
    snapshot_pids = {row["pid"] for row in identities}
    if valid_pids and not set(pids).issubset(snapshot_pids):
        errors.append("target_pid_not_in_snapshot")
    return errors


def plan_recovery(
    snap: dict[str, Any],
    assertion: dict[str, Any],
    current_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    snapshot_rows, snapshot_errors = validate_snapshot(snap)
    if snapshot_errors:
        return {
            "schema_version": SCHEMA,
            "ok": False,
            "classification": "invalid_snapshot",
            "errors": snapshot_errors,
            "execution_performed": False,
        }
    errors = validate_operator_assertion(assertion, snap)
    if errors:
        return {
            "schema_version": SCHEMA,
            "ok": False,
            "classification": "operator_assertion_rejected",
            "errors": errors,
            "execution_performed": False,
        }

    targets = set(int(pid) for pid in assertion["target_pids"])
    expected = {row["pid"]: row for row in snapshot_rows if row["pid"] in targets}
    try:
        current_identities = [_identity(row) for row in current_rows]
    except (KeyError, TypeError, ValueError):
        return {
            "schema_version": SCHEMA,
            "ok": False,
            "classification": "current_inventory_invalid",
            "execution_performed": False,
        }
    current = {row["pid"]: row for row in current_identities if row["pid"] in targets}
    mismatched = [pid for pid in current if current[pid] != expected[pid]]
    if mismatched:
        return {
            "schema_version": SCHEMA,
            "ok": False,
            "classification": "target_identity_changed",
            "mismatched_pids": sorted(mismatched),
            "execution_performed": False,
        }

    unsafe = [
        pid for pid, row in current.items()
        if row["name"] not in ALLOWED_NAMES or not row["runtime_marker"] or row["parent_name"] != "codex.exe"
    ]
    if unsafe:
        return {
            "schema_version": SCHEMA,
            "ok": False,
            "classification": "unsafe_target_rejected",
            "unsafe_pids": sorted(unsafe),
            "execution_performed": False,
        }

    live = sorted(current)
    already_gone = sorted(targets - set(live))
    return {
        "schema_version": SCHEMA,
        "ok": True,
        "classification": "recovery_plan_ready" if live else "already_gone",
        "planned_pids": live,
        "already_gone_pids": already_gone,
        "execution_performed": False,
        "approval_verified": False,
        "approval_verification_owner": "trusted_runtime_outside_this_package",
        "next_action": "trusted_runtime_reverify_identity_obtain_human_approval_then_execute_and_read_back",
        "runtime_healthy": "unknown_until_smoke",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--output")
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--snapshot", required=True)
    plan_parser.add_argument("--operator-assertion", required=True)
    args = parser.parse_args()

    if os.name != "nt":
        result = {
            "schema_version": SCHEMA,
            "ok": False,
            "classification": "unsupported_platform",
            "supported_platform": "windows",
            "execution_performed": False,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    if args.command == "inspect":
        result = snapshot(inventory())
        if args.output:
            Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        snap = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        assertion = json.loads(Path(args.operator_assertion).read_text(encoding="utf-8"))
        result = plan_recovery(snap, assertion, inventory())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
