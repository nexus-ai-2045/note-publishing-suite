"""The adopted rule must survive dropped frontmatter and optional history."""
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location("kuten_test_" + name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


POLICY = {"schema": "nps-linebreak-policy/v1", "after_kuten": True}


def workspace(tmp_path):
    (tmp_path / "voice.md").write_text("句点の後は段落内改行。", encoding="utf-8")
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"schema_version": "nps-workspace-settings/v1", "workspace_root": ".",
        "storage": {"drafts": ".", "sources": ".", "feedback": "feedback"},
        "style": {"default_profile": "voice.md", "article_profiles": {},
                  "linebreak_policy": POLICY}}))
    return settings


def test_author_policy_cannot_be_weakened_by_article():
    gate = load("note_linebreak_gate")
    result = gate.resolve_policy({"linebreak_policy": POLICY,
        "article_profiles": {"article": {"linebreak_policy": {**POLICY, "after_kuten": False}}}}, "article")
    assert result["after_kuten"] is True


def test_html_source_newline_does_not_count_as_visible_br():
    result = load("note_linebreak_gate").validate_live_html("<p>一文です。\n次の文です。</p>", POLICY)
    assert result["ok"] is False
    assert result["paragraph_soft_break_counts"] == [0]


def test_html_trailing_br_cannot_be_hidden_by_observed_zero_count():
    result = load("note_linebreak_gate").validate_live_html("<p>一文です。<br></p>", POLICY)
    assert result["ok"] is False
    assert result["trailing_plain_br_count"] == 1
    clean = load("note_linebreak_gate").validate_live_html("<p>一文です。<br>次の文です。</p>", POLICY)
    assert clean["ok"] is True
    assert clean["trailing_plain_br_count"] == 0


def test_url_mask_does_not_swallow_following_japanese_prose():
    result = load("note_linebreak_gate").validate_draft("参照 https://example.com。次の説明です。続きです。", POLICY)
    assert result["ok"] is False


def test_article_only_policy_requires_article_id(tmp_path):
    settings = workspace(tmp_path)
    config = json.loads(settings.read_text())
    config["style"].pop("linebreak_policy")
    config["style"]["article_profiles"] = {"article": {"references": [], "linebreak_policy": POLICY}}
    settings.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="article-id"):
        load("note_workflow_gate").read_workspace_settings(settings, "")
    draft = tmp_path / "draft.md"
    draft.write_text("一文です。次の文です。")
    assert load("note_authorship_gate").check_history_learning_from_settings(draft, settings, None)["status"] == "blocked"


@pytest.mark.parametrize("flag", [None, False])
def test_dropped_or_false_frontmatter_cannot_bypass_settings(tmp_path, flag):
    settings = workspace(tmp_path)
    text = "一文です。次の文です。\n"
    if flag is not None:
        text = "---\nauthor_style:\n  linebreak_after_kuten: false\n---\n" + text
    draft = tmp_path / "draft.md"
    draft.write_text(text)
    result = load("note_authorship_gate").check_history_learning_from_settings(draft, settings, "article")
    assert result["status"] == "blocked"
    assert "kuten_linebreak_missing" in result["errors"]


def test_draft_accepts_break_after_quote_and_ignores_fenced_code():
    gate = load("note_linebreak_gate")
    assert gate.validate_draft('「一文です。」\n次の文です。\n\n```\n例。コード\n```\n', POLICY)["ok"]
    assert not gate.validate_draft('```\n例。本文\n', POLICY)["ok"]


def test_workflow_checks_linebreaks_without_history_required(tmp_path):
    settings = workspace(tmp_path)
    workflow = load("note_workflow_gate")
    expected, _ = workflow.read_workspace_settings(settings, "article")
    assert expected["linebreak_policy"] == POLICY
    for name in ["source", "draft", "proposed"]:
        (tmp_path / (name + ".md")).write_text("一文です。次の文です。")
    packet = {"schema_version": workflow.SCHEMA, "article_id": "article", "conversation_id": "current",
        "route": "direct_draft", "receipts": [], "ssot_readback": expected,
        "source_snapshot": str(tmp_path / "source.md"), "draft": str(tmp_path / "draft.md"),
        "proposed_draft": str(tmp_path / "proposed.md"), "edit_plan": {}, "settings": {"account": "fixture"}}
    result = workflow.check_packet(packet, "edit", "current", tmp_path, settings_path=settings)
    assert result["linebreak_check"]["ok"] is False
    assert "linebreak: kuten_linebreak_missing" in result["reasons"]


@pytest.mark.parametrize("body", [None, "", "<p>一文です。次の文です。</p>"])
def test_final_cycle_cannot_use_absent_or_unbroken_html(tmp_path, body):
    settings = workspace(tmp_path)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps({"schema": "note-editor-pdca-cycle-receipt/v1", "state": "completed",
        "cycles": [], "linebreak_observation": {"body_html": body,
        "expected_paragraph_soft_break_counts": [0]}}))
    result = load("note_editor_pdca_cycle_check").check(path, settings_path=settings, article_id="article")
    assert result["ok"] is False
    assert any("linebreak:" in error for error in result["errors"])


def test_final_cycle_detects_sentence_per_paragraph_reformat(tmp_path):
    settings = workspace(tmp_path)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps({"schema": "note-editor-pdca-cycle-receipt/v1", "state": "completed",
        "cycles": [], "linebreak_observation": {"body_html": "<p>一文です。</p><p>次の文です。</p>",
        "expected_paragraph_soft_break_counts": [1]}}))
    result = load("note_editor_pdca_cycle_check").check(path, settings_path=settings, article_id="article")
    assert "linebreak: expected source paragraph structure missing or mismatched" in result["errors"]


def test_prepublish_inherits_policy_even_when_observation_omits_it(tmp_path):
    settings = workspace(tmp_path)
    result = load("note_editor_prepublish_verify").build_result(
        {"article_lane": "production_candidate", "body_html": "<p>一文です。次の文です。</p>"},
        settings_path=settings, article_id="article")
    assert "kuten_linebreak_missing" in {issue["code"] for issue in result["issues"]}


@pytest.mark.parametrize("text", ["[一文です。](https://example.com)",
                                 "[一文です。](https://example.com/a(b))"])
def test_markdown_link_sentence_end_is_visible_end(text):
    gate = load("note_linebreak_gate")
    assert gate.validate_draft(text, POLICY)["ok"]
    assert not gate.validate_draft(text + "次の文です。", POLICY)["ok"]


@pytest.mark.parametrize("html", ["<ul><li>親です。<ul><li>子です。</li></ul></li></ul>",
                                 "<ul><li><p>親です。</p><ul><li><p>子です。</p></li></ul></li></ul>"])
def test_nested_list_items_are_independent_blocks(html):
    result = load("note_linebreak_gate").validate_live_html(html, POLICY)
    assert result["ok"]
    assert result["paragraph_soft_break_counts"] == [0, 0]


def test_cycle_without_adopted_policy_does_not_require_article_id(tmp_path):
    settings = workspace(tmp_path)
    config = json.loads(settings.read_text())
    config["style"].pop("linebreak_policy")
    settings.write_text(json.dumps(config))
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps({"schema": "note-editor-pdca-cycle-receipt/v1", "state": "completed", "cycles": []}))
    result = load("note_editor_pdca_cycle_check").check(path, settings_path=settings)
    assert not any("linebreak" in error for error in result["errors"])


def test_workflow_blocks_invalid_utf8(tmp_path):
    settings = workspace(tmp_path)
    workflow = load("note_workflow_gate")
    expected, _ = workflow.read_workspace_settings(settings, "article")
    (tmp_path / "draft.md").write_bytes(b"\xff")
    (tmp_path / "source.md").write_text("source")
    packet = {"schema_version": workflow.SCHEMA, "article_id": "article", "conversation_id": "current",
        "route": "direct_draft", "receipts": [], "ssot_readback": expected,
        "source_snapshot": str(tmp_path / "source.md"), "draft": str(tmp_path / "draft.md")}
    result = workflow.check_packet(packet, "research", "current", tmp_path, settings_path=settings)
    assert result["status"] == "blocked"
    assert "linebreak: draft must be valid UTF-8" in result["reasons"]
