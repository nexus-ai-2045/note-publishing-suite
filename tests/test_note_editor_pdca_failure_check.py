#!/usr/bin/env python3
"""公開物へ実台帳を含めず、Note editor PDCA schemaを検証する。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def valid_ledger() -> dict:
    failures = [
        "browser_clipboard_image_paste_no_insert",
        "browser_clipboard_native_pipe_closed",
        "visible_file_dialog_delayed_multi_insert",
        "direct_input_file_api_unavailable",
        "cursor_drift_or_ambiguous_placeholder",
        "stale_memory_state",
        "unexpected_navigation_or_already_completed",
    ]
    evidence = [
        "goal", "route_id", "browser_surface", "ai_surface",
        "target_note_url_or_id", "fresh_dom_observed_at",
        "figure_count_before", "figure_count_after",
        "target_heading_or_placeholder", "cursor_or_selection",
        "check_result", "act_next_step",
        "public_or_schedule_or_share_not_clicked", "url_and_title_before",
        "dom_snapshot_before", "locator_candidate_count", "url_and_title_after",
        "dom_snapshot_after", "state_transition_classification",
    ]
    return {
        "public_action_allowed": False,
        "retry_policy": {
            "max_same_route_attempts": 2,
            "fresh_dom_required_before_retry": True,
            "same_failure_closes_route_for_article": True,
            "delayed_multi_change_forces_reaudit": True,
            "memory_only_state_forbidden": True,
        },
        "required_cycle_evidence": evidence,
        "failure_patterns": [
            {
                "failure_id": failure_id,
                "route_id": "synthetic-route",
                "symptom": "synthetic symptom",
                "cause": "synthetic cause",
                "stopline": "stop",
                "next_action": "re-audit",
                "must_record": ["fresh_dom_observed_at"],
            }
            for failure_id in failures
        ],
    }


def run_checker(tmp_path: Path, ledger: dict) -> tuple[int, dict]:
    path = tmp_path / "synthetic-ledger.json"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/note_editor_pdca_failure_check.py"),
            "--ledger", str(path), "--skip-docs", "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode, json.loads(result.stdout)


def test_synthetic_ledger_passes_without_publication_actions(tmp_path):
    returncode, payload = run_checker(tmp_path, valid_ledger())
    assert returncode == 0
    assert payload["ok"] is True
    assert payload["residual_work_zero"] is True
    assert payload["external_actions_performed"] == []
    assert payload["publication_actions_performed"] == []


def test_retry_policy_drift_fails_closed(tmp_path):
    ledger = valid_ledger()
    ledger["retry_policy"]["max_same_route_attempts"] = 3
    returncode, payload = run_checker(tmp_path, ledger)
    assert returncode == 1
    assert any("max_same_route_attempts" in item for item in payload["stop_causes"])


def test_missing_fresh_dom_evidence_fails_closed(tmp_path):
    ledger = valid_ledger()
    ledger["required_cycle_evidence"].remove("fresh_dom_observed_at")
    returncode, payload = run_checker(tmp_path, ledger)
    assert returncode == 1
    assert any("fresh_dom_observed_at" in item for item in payload["stop_causes"])


def test_default_package_ledger_and_docs_pass():
    """Synthetic path だけ通しても default ledger が欠けると運用保証にならない。"""
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/note_editor_pdca_failure_check.py"),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["residual_work_zero"] is True
    assert payload["external_actions_performed"] == []
    assert payload["publication_actions_performed"] == []
    assert "note_editor_pdca_failure_patterns.json" in payload["ledger"]
