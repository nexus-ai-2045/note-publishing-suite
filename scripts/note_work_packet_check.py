#!/usr/bin/env python3
"""Validate a Note work packet before dispatch and closeout.

This is a routing/closeout contract, not an editor or publication action.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = (
    "task_id",
    "meta_label",
    "fde_label",
    "owner",
    "chain_from",
    "return_to",
    "objective",
    "input",
    "expected_output",
    "done_when",
    "stop_when",
    "status",
    "evidence",
    "residual",
    "next_action",
)
ALLOWED_STATUS = {
    "planned",
    "dispatched",
    "delivered",
    "collected",
    "accepted",
    "closed",
    "blocked",
    "unknown",
}


def load_packet(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("packet root must be an object")
    return data


def validate_packet(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if packet.get("schema_version") != "note-work-packet/v1":
        errors.append("schema_version must be note-work-packet/v1")
    for field in REQUIRED_FIELDS:
        value = packet.get(field)
        if value is None or value == "" or (value == [] and field != "residual"):
            errors.append(f"{field} must be present and non-empty")
    status = packet.get("status")
    if status not in ALLOWED_STATUS:
        errors.append(f"status must be one of {sorted(ALLOWED_STATUS)}")
    if not isinstance(packet.get("evidence"), list):
        errors.append("evidence must be a list")
    if not isinstance(packet.get("residual"), list):
        errors.append("residual must be a list")
    if status in {"accepted", "closed"}:
        if not packet.get("evidence"):
            errors.append("accepted/closed packet requires evidence")
        if packet.get("residual"):
            errors.append("accepted/closed packet cannot have residual work")
    if status in {"blocked", "unknown"} and not packet.get("next_action"):
        errors.append("blocked/unknown packet requires next_action")
    evidence_paths = packet.get("evidence_paths", [])
    if not isinstance(evidence_paths, list):
        errors.append("evidence_paths must be a list")
    else:
        for raw_path in evidence_paths:
            if not isinstance(raw_path, str) or not raw_path.strip():
                errors.append("evidence_paths entries must be non-empty strings")
            elif not Path(raw_path).is_file():
                errors.append(f"evidence path does not exist: {raw_path}")
    return errors


def build_result(packet_path: Path) -> dict[str, Any]:
    try:
        packet = load_packet(packet_path)
        stop_causes = validate_packet(packet)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        packet = {}
        stop_causes = [str(exc)]
    return {
        "ok": not stop_causes,
        "residual_work_zero": not stop_causes and not packet.get("residual"),
        "packet": str(packet_path),
        "status": packet.get("status", "unknown"),
        "stop_causes": stop_causes,
        "external_actions_performed": [],
        "publication_actions_performed": [],
        "guarantee_scope": "routing_and_closeout_contract_only_no_editor_or_publication_write",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Note work packet contract.")
    parser.add_argument("packet", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = build_result(args.packet)
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
