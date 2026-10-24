import copy
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from note_editor_prepublish_verify import build_result


def observation():
    return {
        "article_lane": "production_candidate",
        "note_id": "n123", "draft_saved": True,
        "manual_publish_required": True, "send_button_automation_allowed": False,
        "observed_at": "2026-09-22T12:00:00Z", "browser_surface": "iab",
        "top_image": {"present": True}, "toc_count": 1,
        "editor_structure": {"h2_count": 2, "h3_count": 0, "heading_order": [2,2], "toc_count": 1, "toc_ref_count": 2},
        "save_readback": {"saved_at": "2026-09-22T11:59:00Z", "observed_at": "2026-09-22T12:00:00Z", "same_note_id": True, "reloaded_or_reclaimed": True, "expected_invariants_verified": True},
        "tags": ["test"], "magazine": {"added": True}, "article_type": "無料",
        "final_buttons": [{"label": "投稿する", "clicked": False, "automation_allowed": False}],
        "edit_session": {
            "image_edits": [{"block_id": "image-1", "neighbors_verified": True, "text_unchanged": True, "introduced_empty_paragraphs": 0}],
            "settings_visit_id": "visit-2",
            "publish_settings": {"visit_id": "visit-2", "observed_at": "2026-09-22T12:01:00Z", "tags": ["test"], "magazine": {"added": True}, "contest_entries": []},
        },
    }


def test_complete_session_passes():
    assert build_result(observation())["ready_for_publish"] is True


@pytest.mark.parametrize("change,code", [
    (lambda o: o.pop("edit_session"), "edit_session_missing"),
    (lambda o: o["edit_session"].pop("image_edits"), "image_edits_unknown"),
    (lambda o: o["edit_session"]["image_edits"][0].update(introduced_empty_paragraphs=1), "image_empty_paragraphs"),
    (lambda o: o["edit_session"]["image_edits"][0].update(text_unchanged=False), "image_context_unverified"),
    (lambda o: o["edit_session"].update(settings_visit_id="visit-3"), "publish_settings_stale"),
    (lambda o: o["edit_session"]["publish_settings"].update(observed_at="2026-09-22T11:58:00Z"), "publish_settings_before_readback"),
    (lambda o: o["edit_session"]["publish_settings"].update(tags=[]), "publish_settings_mismatch"),
    (lambda o: o["edit_session"]["publish_settings"].pop("contest_entries"), "contest_entries_unknown"),
    (lambda o: o["edit_session"]["publish_settings"].update(contest_entries=[{"tag": "test", "popup_resolved": False, "participation_confirmed": True}]), "contest_entry_unconfirmed"),
])
def test_session_failure_or_unknown_blocks_ready(change, code):
    data = observation()
    change(data)
    result = build_result(data)
    assert result["ready_for_publish"] is False
    assert code in {i["code"] for i in result["issues"]}


def test_no_image_change_and_confirmed_contest():
    data = observation()
    data["edit_session"]["image_edits"] = []
    data["edit_session"]["publish_settings"]["contest_entries"] = [{"tag": "test", "popup_resolved": True, "participation_confirmed": True}]
    assert build_result(data)["ready_for_publish"] is True


def test_missing_both_tag_observations_is_unknown():
    data = observation()
    data.pop("tags")
    data["edit_session"]["publish_settings"].pop("tags")
    result = build_result(data)
    assert result["ready_for_publish"] is False
    assert "publish_tags_unknown" in {i["code"] for i in result["issues"]}


def test_null_tags_with_contest_fails_without_exception():
    data = observation()
    data["tags"] = None
    data["edit_session"]["publish_settings"]["tags"] = None
    data["edit_session"]["publish_settings"]["contest_entries"] = [{"tag": "test"}]
    assert build_result(data)["ready_for_publish"] is False
