import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("cycle_check", ROOT / "scripts/note_editor_pdca_cycle_check.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

def valid_cycle():
    return {"goal":"画像候補を照合する","route_id":"audit_only","browser_surface":"in_app_browser","ai_surface":"codex_main","target_note_url_or_id":"n123","fresh_dom_observed_at":"2026-09-21T20:00:00+09:00","figure_count_before":6,"figure_count_after":6,"target_heading_or_placeholder":"AI総量","cursor_or_selection":"none","check_result":"match","act_next_step":"stop","public_or_schedule_or_share_not_clicked":True,"url_and_title_before":"editor/n123 | title","dom_snapshot_before":"sha256:before","locator_candidate_count":1,"url_and_title_after":"editor/n123 | title","dom_snapshot_after":"sha256:after","state_transition_classification":"unchanged","action_count":1}

def receipt(tmp_path, data):
    path = tmp_path / "receipt.json"; path.write_text(json.dumps(data), encoding="utf-8"); return path

def test_valid_completed_receipt_passes(tmp_path):
    result = MODULE.check(receipt(tmp_path, {"schema": MODULE.SCHEMA, "state":"completed", "cycles":[valid_cycle()]}), True)
    assert result["ok"] is True and result["external_actions_performed"] == []

def test_missing_fresh_observation_fails_closed(tmp_path):
    cycle = valid_cycle(); cycle.pop("fresh_dom_observed_at")
    result = MODULE.check(receipt(tmp_path, {"schema": MODULE.SCHEMA, "state":"completed", "cycles":[cycle]}))
    assert not result["ok"] and any("fresh_dom_observed_at" in item for item in result["errors"])

def test_third_same_route_attempt_fails_closed(tmp_path):
    result = MODULE.check(receipt(tmp_path, {"schema": MODULE.SCHEMA, "state":"completed", "cycles":[valid_cycle(), valid_cycle(), valid_cycle()]}))
    assert not result["ok"] and any("exceeds two attempts" in item for item in result["errors"])

def test_open_receipt_needs_final_when_requested(tmp_path):
    result = MODULE.check(receipt(tmp_path, {"schema": MODULE.SCHEMA, "state":"open", "cycles":[valid_cycle()]}), True)
    assert not result["ok"] and any("final state required" in item for item in result["errors"])
