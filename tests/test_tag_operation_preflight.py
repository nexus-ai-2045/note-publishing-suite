from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

@pytest.fixture
def tag_readback():
    baseline = dict(article_id="nexample", account="example", selected_tags=["AI"],
                    suggested_tags=["フェス"], selection_scope_verified=True)
    return dict(baseline=baseline, current=dict(baseline), planned_additions=["AI", "フェス"])


def test_tag_preflight_distinguishes_candidate_and_skips_existing(tag_readback):
    from note_editor_prepublish_verify import tag_operation_preflight
    result = tag_operation_preflight(tag_readback, "nexample", "example")
    assert result["status"] == "approved"
    assert result["additions"] == ["フェス"]
    assert result["skipped"] == ["AI"]
    assert result["automation_allowed"] is False


@pytest.mark.parametrize("field,value,reason", [
    ("selected_tags", ["AI", "自由"], "tag_selected_changed_since_baseline"),
    ("article_id", "other", "tag_identity_mismatch:current"),
    ("account", "other", "tag_identity_mismatch:current"),
    ("selection_scope_verified", False, "tag_selected_region_unverified:current"),
    ("selected_tags", ["AI", "#AI"], "tag_selected_duplicate:current"),
])
def test_tag_preflight_stops_before_mutation(tag_readback, field, value, reason):
    from note_editor_prepublish_verify import tag_operation_preflight, validate_tag_preflight
    tag_readback["current"][field] = value
    result = tag_operation_preflight(tag_readback, "nexample", "example")
    assert result["status"] == "blocked"
    assert result["additions"] == []
    assert reason in result["reasons"]
    errors = validate_tag_preflight(dict(note_id="nexample", account="example", tag_preflight=tag_readback))
    assert reason in [e["code"] for e in errors]


@pytest.mark.parametrize("bad", [None, {}, {"baseline": None}, {"planned_additions": "AI"}])
def test_tag_preflight_invalid_observation_fails_closed(bad):
    from note_editor_prepublish_verify import tag_operation_preflight
    assert tag_operation_preflight(bad, "nexample", "example")["status"] == "blocked"


def test_supplied_snapshot_qa_includes_tag_preflight(tag_readback):
    from note_editor_prepublish_verify import build_result
    tag_readback["current"]["selected_tags"] = ["AI", "自由"]
    result = build_result(dict(note_id="nexample", account="example", tag_preflight=tag_readback))
    assert result["ok"] is False
    assert "tag_selected_changed_since_baseline" in [item["code"] for item in result["issues"]]
