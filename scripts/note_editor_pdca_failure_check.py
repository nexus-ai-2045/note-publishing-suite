#!/usr/bin/env python3
"""Validate the Note editor PDCA failure-pattern ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "data/note_editor_pdca_failure_patterns.json"
PDCA_PATH = ROOT / "references/note-editor-pdca-orchestration.md"
OPS_PATH = ROOT / "skills/note-editor-ops/SKILL.md"

REQUIRED_FAILURES = {
    "browser_clipboard_image_paste_no_insert",
    "browser_clipboard_native_pipe_closed",
    "visible_file_dialog_delayed_multi_insert",
    "direct_input_file_api_unavailable",
    "cursor_drift_or_ambiguous_placeholder",
    "stale_memory_state",
    "unexpected_navigation_or_already_completed",
}

REQUIRED_RETRY_POLICY = {
    "max_same_route_attempts": 2,
    "fresh_dom_required_before_retry": True,
    "same_failure_closes_route_for_article": True,
    "delayed_multi_change_forces_reaudit": True,
    "memory_only_state_forbidden": True,
}

REQUIRED_CYCLE_EVIDENCE = {
    "goal",
    "route_id",
    "browser_surface",
    "ai_surface",
    "target_note_url_or_id",
    "fresh_dom_observed_at",
    "figure_count_before",
    "figure_count_after",
    "target_heading_or_placeholder",
    "cursor_or_selection",
    "check_result",
    "act_next_step",
    "public_or_schedule_or_share_not_clicked",
    "url_and_title_before",
    "dom_snapshot_before",
    "locator_candidate_count",
    "url_and_title_after",
    "dom_snapshot_after",
    "state_transition_classification",
}


def load_ledger(path: Path = LEDGER_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("ledger root must be an object")
    return data


def validate_ledger(ledger: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if ledger.get("public_action_allowed") is not False:
        errors.append("public_action_allowed must be false")

    retry_policy = ledger.get("retry_policy")
    if not isinstance(retry_policy, dict):
        errors.append("retry_policy must be an object")
    else:
        for key, expected in REQUIRED_RETRY_POLICY.items():
            if retry_policy.get(key) != expected:
                errors.append(f"retry_policy.{key} must be {expected!r}")

    cycle_evidence = set(ledger.get("required_cycle_evidence") or [])
    missing_evidence = REQUIRED_CYCLE_EVIDENCE - cycle_evidence
    if missing_evidence:
        errors.append("required_cycle_evidence missing: " + ", ".join(sorted(missing_evidence)))

    patterns = ledger.get("failure_patterns")
    if not isinstance(patterns, list) or not patterns:
        errors.append("failure_patterns must be a non-empty list")
        return errors

    by_id = {
        item.get("failure_id"): item
        for item in patterns
        if isinstance(item, dict) and isinstance(item.get("failure_id"), str)
    }
    missing_failures = REQUIRED_FAILURES - set(by_id)
    if missing_failures:
        errors.append("failure_patterns missing: " + ", ".join(sorted(missing_failures)))

    for failure_id, item in by_id.items():
        for key in ["route_id", "symptom", "cause", "stopline", "next_action"]:
            if not item.get(key):
                errors.append(f"failure_patterns.{failure_id}.{key} must be non-empty")
        must_record = item.get("must_record")
        if not isinstance(must_record, list) or not must_record:
            errors.append(f"failure_patterns.{failure_id}.must_record must be non-empty")

    return errors


def validate_docs() -> list[str]:
    errors: list[str] = []
    required_paths = {
        "references/note-editor-pdca-orchestration.md": PDCA_PATH,
        "skills/note-editor-ops/SKILL.md": OPS_PATH,
        "package.yaml": ROOT / "package.yaml",
    }
    for label, path in required_paths.items():
        if not path.exists():
            errors.append(f"missing {label}")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in [
            "note_editor_pdca_failure_patterns.json",
            "note_editor_pdca_failure_check.py",
        ]:
            if needle not in text:
                errors.append(f"{label} missing: {needle}")

    pdca = PDCA_PATH.read_text(encoding="utf-8") if PDCA_PATH.exists() else ""
    for needle in [
        "fresh DOM",
        "同じ失敗が2回",
        "遅延反映",
        "禁止リトライ",
        "failure ledger",
        "already-completed",
        "action前 URL / title / DOM",
    ]:
        if needle not in pdca:
            errors.append(f"references/note-editor-pdca-orchestration.md missing: {needle}")

    ops = OPS_PATH.read_text(encoding="utf-8") if OPS_PATH.exists() else ""
    for needle in ["Chrome DOM 基本ループ", "候補数が1件", "fresh DOM snapshot", "already-completed", "重複する作成、投稿、公開 click を行わない"]:
        if needle not in ops:
            errors.append(f"skills/note-editor-ops/SKILL.md missing: {needle}")

    return errors


def build_result(
    ledger_path: Path = LEDGER_PATH, *, validate_documentation: bool = True
) -> dict[str, Any]:
    stop_causes: list[str] = []
    ledger = load_ledger(ledger_path)
    stop_causes.extend(validate_ledger(ledger))
    if validate_documentation:
        stop_causes.extend(validate_docs())

    return {
        "ok": not stop_causes,
        "residual_work_zero": not stop_causes,
        "ledger": str(ledger_path),
        "external_actions_performed": [],
        "publication_actions_performed": [],
        "stop_causes": stop_causes,
        "guarantee_scope": "failure_pattern_ledger_only_no_editor_write",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Note editor PDCA failure patterns.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--ledger",
        type=Path,
        default=LEDGER_PATH,
        help="検証する失敗パターンJSON。公開パッケージ外の運用台帳も指定できます。",
    )
    parser.add_argument(
        "--skip-docs",
        action="store_true",
        help="台帳スキーマだけを検証し、非公開文書への参照確認を省略します。",
    )
    args = parser.parse_args()

    result = build_result(args.ledger, validate_documentation=not args.skip_docs)
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
