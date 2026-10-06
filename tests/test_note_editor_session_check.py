from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from note_editor_prepublish_verify import build_result
from note_editor_session_check import validate_edit_session


def observation() -> dict:
    return {
        "article_lane": "production_candidate",
        "article_id": "fixture-article",
        "top_image": {"present": True},
        "toc_count": 1,
        "production_plan": {
            "article_id": "fixture-article",
            "reader": "fixture reader",
            "series": "fixture-series",
            "reader_action": "fixture action",
            "links": [],
            "review": {
                "status": "approved",
                "reviewer": "fixture-human",
                "reviewed_at": "2026-01-01T00:00:00+00:00",
                "plan_sha256": "fixture",
            },
        },
        "footer": {"nodes": []},
        "magazine": {"added": True},
        "tags": ["test"],
        "article_type": "無料",
        "final_buttons": [{"label": "投稿する", "clicked": False}],
        "save_readback": {"observed_at": "2026-09-22T12:00:00Z"},
        "edit_session": {
            "image_edits": [{"block_id": "image-1", "neighbors_verified": True, "text_unchanged": True, "introduced_empty_paragraphs": 0}],
            "settings_visit_id": "visit-2",
            "publish_settings": {"visit_id": "visit-2", "observed_at": "2026-09-22T12:01:00Z", "tags": ["test"], "magazine": {"added": True}, "contest_entries": []},
        },
    }


def test_complete_session_is_part_of_prepublish_result():
    result = build_result(observation())
    assert validate_edit_session(observation()) == []
    assert "edit_session_missing" not in {item["code"] for item in result["issues"]}


@pytest.mark.parametrize("change,code", [
    (lambda data: data.pop("edit_session"), "edit_session_missing"),
    (lambda data: data["edit_session"].update(settings_visit_id="visit-3"), "publish_settings_stale"),
    (lambda data: data["edit_session"]["publish_settings"].update(tags=[]), "publish_settings_mismatch"),
    (lambda data: data["edit_session"]["publish_settings"].pop("contest_entries"), "contest_entries_unknown"),
])
def test_unknown_or_stale_session_blocks(change, code):
    data = observation()
    change(data)
    result = build_result(data)
    assert result["ok"] is False
    assert code in {item["code"] for item in result["issues"]}


def test_non_production_lane_does_not_require_session():
    data = observation()
    data["article_lane"] = "exploratory_draft"
    data.pop("edit_session")
    assert "edit_session_missing" not in {item["code"] for item in build_result(data)["issues"]}
