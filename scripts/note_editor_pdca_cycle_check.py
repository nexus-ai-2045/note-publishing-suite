#!/usr/bin/env python3
"""Validate one-action Note editor PDCA cycle receipts without operating Note."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:  # script execution
    from note_editor_pdca_failure_check import REQUIRED_CYCLE_EVIDENCE
except ModuleNotFoundError:  # test/import execution from package root
    from scripts.note_editor_pdca_failure_check import REQUIRED_CYCLE_EVIDENCE


SCHEMA = "note-editor-pdca-cycle-receipt/v1"
FINAL_STATES = {"completed", "blocked", "already_completed"}
SUCCESS_CLASSIFICATIONS = {
    "unchanged",
    "state_transition_detected",
    "already_completed",
    "recovered",
}
VALID_CLASSIFICATIONS = SUCCESS_CLASSIFICATIONS | {"blocked"}
COUNT_EVIDENCE = {
    "figure_count_before",
    "figure_count_after",
    "locator_candidate_count",
}
BOOLEAN_EVIDENCE = {"public_or_schedule_or_share_not_clicked"}


def _invalid_evidence(cycle: dict[str, Any]) -> list[str]:
    """Return evidence keys whose values are missing or unusable."""
    bad: list[str] = []
    for key in sorted(REQUIRED_CYCLE_EVIDENCE):
        if key not in cycle:
            bad.append(key)
            continue
        value = cycle[key]
        if key in COUNT_EVIDENCE:
            # bool is a subclass of int; reject True/False explicitly.
            if type(value) is not int or value < 0:
                bad.append(key)
            continue
        if key in BOOLEAN_EVIDENCE:
            if value is None:
                bad.append(key)
            continue
        if not isinstance(value, str) or value == "":
            bad.append(key)
    return bad


def _terminal_cycle(cycles: list[Any]) -> dict[str, Any] | None:
    for item in reversed(cycles):
        if isinstance(item, dict):
            return item
    return None


def _reconcile_receipt_state(
    state: Any, terminal: dict[str, Any] | None, require_final: bool
) -> list[str]:
    """Align top-level receipt state with the terminal cycle classification."""
    if terminal is None:
        return []
    classification = terminal.get("state_transition_classification")
    if state in {"completed", "already_completed"}:
        if classification not in SUCCESS_CLASSIFICATIONS:
            return [
                "completed/already_completed receipts require a successful "
                "terminal state_transition_classification"
            ]
    elif classification == "blocked" and state != "blocked":
        return ["blocked terminal cycle requires receipt state blocked"]
    elif require_final and state == "blocked" and classification != "blocked":
        return [
            "blocked receipts require terminal state_transition_classification blocked"
        ]
    return []


def check(receipt: Path, require_final: bool = False) -> dict[str, Any]:
    try:
        data = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "state": "blocked", "errors": [str(exc)]}
    if not isinstance(data, dict):
        return {"ok": False, "state": "blocked", "errors": ["receipt root must be an object"]}
    errors: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    cycles = data.get("cycles")
    if not isinstance(cycles, list) or not cycles:
        errors.append("cycles must be a non-empty list")
        cycles = []
    routes: Counter[str] = Counter()
    for index, cycle in enumerate(cycles, 1):
        if not isinstance(cycle, dict):
            errors.append(f"cycles[{index}] must be an object")
            continue
        # Counts may be zero. false / [] / {} and other unusable values fail closed.
        bad = _invalid_evidence(cycle)
        if bad:
            errors.append(f"cycles[{index}] missing: {', '.join(bad)}")
        if cycle.get("action_count") != 1:
            errors.append(f"cycles[{index}].action_count must be 1")
        if cycle.get("public_or_schedule_or_share_not_clicked") is not True:
            errors.append(f"cycles[{index}] must confirm public_or_schedule_or_share_not_clicked")
        route = cycle.get("route_id")
        if isinstance(route, str) and route:
            routes[route] += 1
        if cycle.get("state_transition_classification") not in VALID_CLASSIFICATIONS:
            errors.append(f"cycles[{index}].state_transition_classification is invalid")
    for route, attempts in routes.items():
        if attempts > 2:
            errors.append(f"route {route} exceeds two attempts")
    state = data.get("state")
    if state not in FINAL_STATES | {"open"}:
        errors.append("state must be open, completed, blocked, or already_completed")
    if require_final and state not in FINAL_STATES:
        errors.append(f"final state required, got {state}")
    errors.extend(_reconcile_receipt_state(state, _terminal_cycle(cycles), require_final))
    return {
        "ok": not errors,
        "state": state if not errors else "blocked",
        "cycle_count": len(cycles),
        "external_actions_performed": [],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--require-final", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = check(args.receipt, args.require_final)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("OK" if result["ok"] else "NG")
        for error in result["errors"]:
            print(f"- {error}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
