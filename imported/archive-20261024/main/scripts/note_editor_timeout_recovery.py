#!/usr/bin/env python3
"""Plan a fail-closed, idempotent recovery after Note browser timeouts."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


SCHEMA_VERSION = "note-editor-recovery/v1"
RECOVERABLE = {
    "node_repl_transport_closed",
    "browser_runtime_disconnected",
    "cdp_runtime_evaluate_timeout",
    "dom_snapshot_timeout",
    "tab_missing",
}
ROUTES = ("iab", "chrome_extension")


def _count_failures(data: dict[str, Any], route: str, operation_id: str) -> int:
    return sum(
        1
        for attempt in data.get("attempts", [])
        if attempt.get("route") == route
        and attempt.get("operation_id") == operation_id
        and attempt.get("result") == "failed"
    )


def plan_recovery(data: dict[str, Any]) -> dict[str, Any]:
    required = ("target_url", "operation_id", "current_route", "error_code")
    missing = [key for key in required if not data.get(key)]
    if missing:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "classification": "invalid_recovery_state",
            "errors": [f"missing:{key}" for key in missing],
            "next_action": "stop",
        }

    operation_id = str(data["operation_id"])
    route = str(data["current_route"])
    completed = set(data.get("completed_operations", []))
    postconditions = data.get("observed_postconditions", {})

    if operation_id in completed or postconditions.get(operation_id) is True:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": True,
            "classification": "already_completed",
            "next_action": "skip_mutation_and_readback",
            "resume_from": data.get("next_checkpoint"),
            "must_not_repeat": [operation_id],
        }

    error_code = str(data["error_code"])
    if error_code not in RECOVERABLE:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "classification": "unknown_browser_runtime_error",
            "next_action": "stop_and_capture_exact_error",
            "must_not_repeat": [operation_id],
        }

    failures = _count_failures(data, route, operation_id)
    if failures < 2:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": True,
            "classification": "recover_same_route",
            "next_action": "new_session_reinventory_reclaim_readback",
            "discard": ["tab_binding", "browser_binding", "locator"],
            "target_url": data["target_url"],
            "resume_from": data.get("last_verified_checkpoint"),
            "preconditions": [
                "fresh_runtime_smoke",
                "exact_url_tab_count_equals_one",
                "fresh_dom_snapshot",
                "checkpoint_postcondition_readback",
            ],
            "must_not_repeat": list(completed),
        }

    alternate = next(
        (
            candidate
            for candidate in ROUTES
            if candidate != route
            and _count_failures(data, candidate, operation_id) < 2
            and candidate in set(data.get("allowed_routes", ROUTES))
        ),
        None,
    )
    if alternate:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": True,
            "classification": "same_route_closed",
            "next_action": "switch_route_reinventory_reclaim_readback",
            "closed_route": route,
            "selected_route": alternate,
            "target_url": data["target_url"],
            "resume_from": data.get("last_verified_checkpoint"),
            "preconditions": [
                "fresh_runtime_smoke",
                "exact_url_tab_count_equals_one",
                "fresh_dom_snapshot",
                "checkpoint_postcondition_readback",
            ],
            "must_not_repeat": list(completed),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "classification": "recovery_routes_exhausted",
        "next_action": "human_or_runtime_restart_boundary",
        "target_url": data["target_url"],
        "resume_from": data.get("last_verified_checkpoint"),
        "must_not_repeat": [operation_id, *sorted(completed)],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", nargs="?", help="JSON state file; stdin when omitted")
    args = parser.parse_args()
    try:
        if args.state:
            with open(args.state, encoding="utf-8") as handle:
                data = json.load(handle)
        else:
            data = json.load(sys.stdin)
        result = plan_recovery(data)
    except (OSError, json.JSONDecodeError) as exc:
        result = {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "classification": "invalid_recovery_state",
            "errors": [f"{type(exc).__name__}:{exc}"],
            "next_action": "stop",
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
