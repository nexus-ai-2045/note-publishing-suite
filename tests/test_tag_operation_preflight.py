from pathlib import Path
import hashlib
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


@pytest.fixture
def tag_design():
    return dict(schema="note-tag-design/v1", article_id="nexample",
                body_sha256=hashlib.sha256(b"Body").hexdigest(),
                policy=dict(id="nps-local-tags/v1", min_tags=5, max_tags=10),
        strategy={axis: dict(reason="選定時に本文・読者導線・発信方針を照合", evidence_ref=f"review://tags/{axis}")
                  for axis in ("content", "discovery", "branding")},
                tags=[dict(tag=tag, role=role, reason="本文の該当話題へ対応",
                           evidence_ref="draft://section") for tag, role in
                      [("AI", "topic"), ("研究", "topic"), ("ニュース", "context"),
                       ("技術", "context"), ("観測連載", "series")]],
                previous_article=dict(article_id="previous", reference="previous.md#tags",
                                      tags=["AI"], comparison="主題AIを維持し今回の文脈を選定"))


def test_tag_design_binds_current_body_and_normalized_settings(tag_design):
    from note_editor_prepublish_verify import validate_tag_design
    tags = [row["tag"] for row in tag_design["tags"]]
    assert validate_tag_design(tag_design, "nexample", tags, "Body") == []
    assert validate_tag_design(tag_design, "nexample", ["#" + tag for tag in tags], "Body") == []


@pytest.mark.parametrize("mutation", [
    "missing", "empty", "duplicate", "reason", "evidence", "body", "identity", "roles",
    "previous", "comparison", "policy", "wrong_tags", "malformed_row", "null_policy",
])
def test_tag_design_rejects_missing_or_stale_evidence(tag_design, mutation):
    from note_editor_prepublish_verify import validate_tag_design
    tags = [row["tag"] for row in tag_design["tags"]]
    if mutation == "missing": tag_design = None
    elif mutation == "empty": tag_design["tags"] = []
    elif mutation == "duplicate": tag_design["tags"][1]["tag"] = "#AI"
    elif mutation == "reason": tag_design["tags"][0]["reason"] = " "
    elif mutation == "evidence": tag_design["tags"][0].pop("evidence_ref")
    elif mutation == "body": tag_design["body_sha256"] = "0" * 64
    elif mutation == "identity": tag_design["article_id"] = "other"
    elif mutation == "roles": tag_design["tags"][-1]["role"] = "context"
    elif mutation == "previous": tag_design["previous_article"] = None
    elif mutation == "comparison": tag_design["previous_article"]["comparison"] = ""
    elif mutation == "policy": tag_design["policy"]["min_tags"] = 0
    elif mutation == "wrong_tags": tags[0] = "Other"
    elif mutation == "malformed_row": tag_design["tags"][0] = None
    elif mutation == "null_policy": tag_design["policy"] = None
    assert validate_tag_design(tag_design, "nexample", tags, "Body")


def test_tag_design_frontmatter_body_hash_uses_existing_splitter(tag_design):
    from note_editor_prepublish_verify import validate_tag_design
    from pre_publish_check import split_frontmatter
    draft = "---\ntitle: Example\n---\n\nBody"
    tag_design["body_sha256"] = hashlib.sha256(split_frontmatter(draft)[1].encode()).hexdigest()
    assert validate_tag_design(tag_design, "nexample", [r["tag"] for r in tag_design["tags"]], draft) == []


def test_previous_none_requires_reason_and_cannot_pass_continuation(tag_design):
    from note_editor_prepublish_verify import validate_tag_design
    tags = [r["tag"] for r in tag_design["tags"]]
    tag_design["previous_article"] = dict(status="none", reason="連載初回", reference="pack.md#first")
    assert validate_tag_design(tag_design, "nexample", tags, "Body") == []
    assert validate_tag_design(tag_design, "nexample", tags, "Body", article_lane="continuation_article")
    tag_design["previous_article"]["reason"] = ""
    assert validate_tag_design(tag_design, "nexample", tags, "Body")


def test_editor_publish_rejects_suggestions_as_selected(tag_design):
    from note_editor_prepublish_verify import validate_tags
    tags = [r["tag"] for r in tag_design["tags"]]
    selected = dict(article_id="nexample", account="example", selected_tags=[],
                    suggested_tags=tags, selection_scope_verified=True)
    data = dict(stage="publish", note_id="nexample", account="example", tags=tags,
                draft_text="Body", tag_design=tag_design,
                tag_preflight=dict(baseline=dict(selected), current=dict(selected), planned_additions=tags))
    assert "tag_selected_design_mismatch" in [issue["code"] for issue in validate_tags(data)]
    for observed in data["tag_preflight"]["baseline"], data["tag_preflight"]["current"]:
        observed["selected_tags"] = tags
    assert validate_tags(data) == []


def test_editor_settings_requires_design_but_legacy_observation_stays_compatible():
    from note_editor_prepublish_verify import validate_tags
    assert validate_tags(dict(tags=["AI"])) == []
    assert "tag_design_missing" in [issue["code"] for issue in validate_tags(dict(stage="settings", tags=["AI"]))]


def test_continuation_in_frontmatter_cannot_be_overridden(tag_design):
    from note_editor_prepublish_verify import validate_tag_design
    from pre_publish_check import split_frontmatter
    text = "---\narticle_lane: continuation_article\n---\nBody"
    tag_design["body_sha256"] = hashlib.sha256(split_frontmatter(text)[1].encode()).hexdigest()
    tag_design["previous_article"] = dict(status="none", reason="初回扱い", reference="pack.md")
    assert "tag_previous_none_invalid" in validate_tag_design(tag_design, "nexample",
        [r["tag"] for r in tag_design["tags"]], text, article_lane="production_candidate")


@pytest.mark.parametrize("axis", ["content", "discovery", "branding"])
@pytest.mark.parametrize("problem", ["missing", "malformed", "reason", "evidence_ref"])
def test_tag_strategy_requires_all_axes(tag_design, axis, problem):
    from note_editor_prepublish_verify import validate_tag_design
    if problem == "missing": tag_design["strategy"].pop(axis)
    elif problem == "malformed": tag_design["strategy"][axis] = []
    else: tag_design["strategy"][axis].pop(problem)
    assert validate_tag_design(tag_design, "nexample", [r["tag"] for r in tag_design["tags"]], "Body")


@pytest.mark.parametrize("value", [None, "", "  ", " PENDING ", "unknown", "TODO", "tbd", "None", "null", "未確認", "未定", "保留"])
@pytest.mark.parametrize("field", ["reason", "evidence_ref"])
def test_tag_strategy_rejects_placeholders(tag_design, value, field):
    from note_editor_prepublish_verify import validate_tag_design
    tag_design["strategy"]["discovery"][field] = value
    assert validate_tag_design(tag_design, "nexample", [r["tag"] for r in tag_design["tags"]], "Body")


def test_tag_strategy_missing_blocks(tag_design):
    from note_editor_prepublish_verify import validate_tag_design
    tag_design.pop("strategy")
    assert "tag_design_strategy_missing" in validate_tag_design(tag_design, "nexample", [r["tag"] for r in tag_design["tags"]], "Body")


def test_tag_strategy_branding_can_explain_absent_brand_tag(tag_design):
    from note_editor_prepublish_verify import validate_tag_design
    tag_design["strategy"]["branding"] = dict(reason="今回の読者導線は連載名で示すためブランドタグを加えない", evidence_ref="review://branding/approved")
    assert validate_tag_design(tag_design, "nexample", [r["tag"] for r in tag_design["tags"]], "Body") == []
