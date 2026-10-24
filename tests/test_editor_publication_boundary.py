"""Supply explicit synthetic observations; never operate an editor or publish."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from note_editor_prepublish_verify import build_result


def observation(lane):
    plan = dict(article_id="fixture-article", reader="fixture reader", series="fixture-series",
                reader_action="fixture action", links=[], decision="omit", reason="fixture has no links")
    digest = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    plan["review"] = dict(status="approved", reviewer="fixture-human",
                          reviewed_at="2026-01-01T00:00:00+00:00", plan_sha256=digest)
    return dict(article_lane=lane, article_id="fixture-article", series="fixture-series",
                note_id="n123", expected_note_id="n123", screen_url="https://editor.note.com/notes/n123/edit/",
                manual_publish_required=True, send_button_automation_allowed=False, draft_saved=True, publication_state="draft",
                top_image=dict(present=True), toc_count=1, production_plan=plan, footer=dict(nodes=[]),
                magazine=dict(added=True), tags=["fixture"], article_type="無料",
                final_buttons=[dict(label="投稿する", clicked=False)],
                save_readback=dict(saved_at="2026-09-22T11:59:00Z", observed_at="2026-09-22T12:00:00Z",
                                   same_note_id=True, reloaded_or_reclaimed=True, expected_invariants_verified=True),
                edit_session=dict(image_edits=[], settings_visit_id="visit-2",
                                  publish_settings=dict(visit_id="visit-2", observed_at="2026-09-22T12:01:00Z",
                                                        tags=["fixture"], magazine=dict(added=True), contest_entries=[])))


@pytest.mark.parametrize("lane", ["production_candidate", "continuation_article"])
def test_complete_prepublication_observation_is_still_snapshot_only(lane):
    result = build_result(observation(lane))
    assert result["issues"] == []
    assert result["ok"] is True
    assert result["ready_for_publish"] is False
    assert result["live_dom_verified"] is False


FAULTS = [
    (lambda d: d.pop("manual_publish_required"), "manual_publish_required_missing"),
    (lambda d: d.update(manual_publish_required="true"), "manual_publish_required_missing"),
    (lambda d: d.update(send_button_automation_allowed=True), "send_button_automation_allowed"),
    (lambda d: d.update(send_button_automation_allowed="false"), "send_button_automation_allowed"),
    (lambda d: d.update(automation_actions=["publish"]), "publication_action_in_automation_plan"),
    (lambda d: d.update(button_click_plan=["送信"]), "publication_action_in_automation_plan"),
    (lambda d: d.update(automation_plan="publish"), "publication_action_plan_unknown"),
    (lambda d: d.update(expected_note_id="n999"), "note_identity_mismatch"),
    (lambda d: d.update(screen_url="https://editor.note.com/notes/n999/edit/?expected=n123"), "screen_url_note_mismatch"),
    (lambda d: d.update(screen_url="https://note.com.evil.example/notes/n123/edit"), "screen_url_note_mismatch"),
    (lambda d: d.update(note_id=123), "note_identity_invalid"),
    (lambda d: (d.pop("note_id"), d.pop("screen_url")), "note_identity_missing"),
    (lambda d: d.update(draft_saved=False), "draft_save_state_missing"),
    (lambda d: d.update(draft_saved="true"), "draft_save_state_missing"),
    (lambda d: d.pop("save_readback"), "post_save_readback_missing"),
    (lambda d: d["save_readback"].update(observed_at="2026-09-22T11:58:00Z"), "post_save_readback_time_invalid"),
    (lambda d: d["save_readback"].update(saved_at="2026-09-22T11:59:00"), "post_save_readback_missing"),
    (lambda d: d["save_readback"].update(same_note_id=False), "post_save_readback_incomplete"),
    (lambda d: d["save_readback"].update(reloaded_or_reclaimed=False), "post_save_readback_incomplete"),
    (lambda d: d["save_readback"].update(expected_invariants_verified=False), "post_save_readback_incomplete"),
    (lambda d: d.update(publication_actions_performed=["publish"]), "publication_or_external_action_recorded"),
    (lambda d: d.update(external_actions_performed="send"), "publication_or_external_action_recorded"),
    (lambda d: d.update(public_actions_performed={"sent": True}), "publication_or_external_action_recorded"),
    (lambda d: d.update(publication_state="published"), "already_published_or_scheduled"),
    (lambda d: d.update(status="scheduled"), "already_published_or_scheduled"),
    (lambda d: d.pop("edit_session"), "edit_session_missing"),
    (lambda d: d["edit_session"]["publish_settings"].update(tags=[]), "publish_settings_mismatch"),
]


@pytest.mark.parametrize("lane", ["production_candidate", "continuation_article"])
@pytest.mark.parametrize("mutate,code", FAULTS)
def test_unsafe_prepublication_state_blocks_without_any_action(lane, mutate, code):
    data = observation(lane)
    mutate(data)
    result = build_result(data)
    assert result["ok"] is False
    assert code in {i["code"] for i in result["issues"]}
    assert result["publication_actions_performed"] == []
    assert result["ready_for_publish"] is False


def test_footer_only_published_snapshot_is_not_a_prepublication_acceptance():
    data = observation("production_candidate")
    data.update(publication_state="published")
    data.pop("manual_publish_required")
    assert build_result(data)["ok"] is False
    result = build_result(data, footer_only=True)
    assert result["ok"] is True
    assert result["verification_scope"] == "supplied_snapshot_only"
    assert result["ready_for_publish"] is False


@pytest.mark.parametrize("lane", ["production_candidate", "continuation_article"])
@pytest.mark.parametrize("key", ["save_notice", "save_state"])
@pytest.mark.parametrize("notice", ["saved", "failed", "保存しました", "保存されていません"])
def test_save_text_does_not_replace_explicit_save_confirmation(lane, key, notice):
    data = observation(lane)
    data.pop("draft_saved")
    data[key] = notice
    result = build_result(data)
    assert result["ok"] is False
    assert "draft_save_state_missing" in {i["code"] for i in result["issues"]}


@pytest.mark.parametrize("lane", ["production_candidate", "continuation_article"])
@pytest.mark.parametrize("danger", ["published", "scheduled", "posted", "public"])
@pytest.mark.parametrize("key", ["publication_state", "status"])
def test_publication_alias_does_not_hide_dangerous_state(lane, danger, key):
    data = observation(lane)
    data.update(publication_state="draft", status="draft")
    data[key] = " " + danger.upper() + " "
    result = build_result(data)
    assert result["ok"] is False
    assert "already_published_or_scheduled" in {i["code"] for i in result["issues"]}


@pytest.mark.parametrize("key", ["publication_state", "status"])
@pytest.mark.parametrize("invalid", [None, "", [], {}, False, 17])
def test_invalid_state_alias_is_not_hidden_by_other_draft_state(key, invalid):
    data = observation("production_candidate")
    data.update(publication_state="draft", status="draft")
    data[key] = invalid
    assert "publication_state_unknown" in {i["code"] for i in build_result(data)["issues"]}


@pytest.mark.parametrize("lane", ["production_candidate", "continuation_article"])
@pytest.mark.parametrize("key", ["publication_state", "status"])
@pytest.mark.parametrize("state", ["publish", "公開済み", "予約済み", "unpublished", "ready", "unknown", "failed"])
def test_undeclared_publication_state_is_not_assumed_safe(lane, key, state):
    data = observation(lane)
    data.update(publication_state="draft", status="draft")
    data[key] = state
    result = build_result(data)
    assert result["ok"] is False
    assert "publication_state_unknown" in {i["code"] for i in result["issues"]}


@pytest.mark.parametrize("lane", ["production_candidate", "continuation_article"])
@pytest.mark.parametrize("key", ["publication_state", "status"])
@pytest.mark.parametrize("state", ["draft", " DRAFT "])
def test_known_draft_state_remains_compatible(lane, key, state):
    data = observation(lane)
    data[key] = state
    assert build_result(data)["ok"] is True


@pytest.mark.parametrize("lane", ["production_candidate", "continuation_article"])
def test_saved_draft_does_not_prove_unknown_publication_state(lane):
    data = observation(lane)
    data.pop("publication_state")
    assert data["draft_saved"] is True
    result = build_result(data)
    assert result["ok"] is False
    assert "publication_state_unknown" in {i["code"] for i in result["issues"]}


@pytest.mark.parametrize("lane", ["production_candidate", "continuation_article"])
@pytest.mark.parametrize("url", ["https://note.com/", "https://editor.note.com/", "https://note.com/n123",
                                 "https://note.com/help/n123", "https://editor.note.com/notes/n123",
                                 "https://note.com/preview/n123/extra", "https://note.com/preview/n123:fake"])
def test_nonarticle_url_cannot_establish_identity(lane, url):
    data = observation(lane)
    data.pop("note_id")
    data["screen_url"] = url
    assert "screen_url_note_mismatch" in {i["code"] for i in build_result(data)["issues"]}


@pytest.mark.parametrize("expected", [None, "", "   ", 17, {}, " n123 "])
def test_expected_article_is_explicitly_bound(expected):
    data = observation("production_candidate")
    data["expected_note_id"] = expected
    assert build_result(data)["ok"] is False


def test_homepage_without_either_article_identifier_blocks():
    data = observation("production_candidate")
    data.pop("note_id")
    data.pop("expected_note_id")
    data["screen_url"] = "https://note.com/"
    assert build_result(data)["ok"] is False


def test_url_aliases_are_independently_bound_to_expected_article():
    data = observation("production_candidate")
    data["url"] = "https://note.com/creator/n/n999"
    assert "screen_url_note_mismatch" in {i["code"] for i in build_result(data)["issues"]}


@pytest.mark.parametrize("url", ["https://editor.note.com/notes/n123/edit/",
                                 "https://note.com/creator/n/n123", "https://note.com/preview/n123"])
def test_canonical_article_url_can_supply_observed_identifier(url):
    data = observation("production_candidate")
    data.pop("note_id")
    data["screen_url"] = url
    assert build_result(data)["ok"] is True


@pytest.mark.parametrize("key", ["automation_actions", "automation_plan", "button_click_plan", "planned_actions", "allowed_actions"])
@pytest.mark.parametrize("action", ["post", "postNote", "schedule", "schedulePublish", "schedule_publish", "click_publish_button", "送信"])
def test_publication_plan_aliases_block_in_every_action_field(key, action):
    data = observation("production_candidate")
    data[key] = [action]
    assert "publication_action_in_automation_plan" in {i["code"] for i in build_result(data)["issues"]}


@pytest.mark.parametrize("invalid", [None, 42, False, {}, [], "", "   "])
def test_malformed_action_elements_are_not_stringified_as_safe(invalid):
    data = observation("production_candidate")
    data["planned_actions"] = [invalid]
    assert "publication_action_plan_unknown" in {i["code"] for i in build_result(data)["issues"]}


@pytest.mark.parametrize("action", ["read_only", "read-only", "open_settings", "settings-open",
                                    "open_publish_settings", "open_publication_settings",
                                    "read_publication_settings", "inspect_publish_settings",
                                    "公開設定を開く", "公開設定を確認", "write_draft", "save_draft"])
def test_readonly_settings_operations_are_not_publication(action):
    data = observation("production_candidate")
    data["planned_actions"] = [action]
    assert build_result(data)["ok"] is True


@pytest.mark.parametrize("lane", ["production_candidate", "continuation_article"])
@pytest.mark.parametrize("key", ["automation_actions", "automation_plan", "button_click_plan", "planned_actions", "allowed_actions"])
@pytest.mark.parametrize("action", ["repost", "crosspost", "xpost", "post_to_x", "unknown_operation", "postprocess_preview"])
def test_undeclared_action_is_not_inferred_safe(lane, key, action):
    data = observation(lane)
    data[key] = [action]
    result = build_result(data)
    assert result["ok"] is False
    assert {"publication_action_in_automation_plan", "publication_action_plan_unknown"} & {i["code"] for i in result["issues"]}


@pytest.mark.parametrize("lane", ["editor_fixture", "exploratory_draft"])
def test_explicit_nonproduction_snapshot_does_not_require_production_boundary(lane):
    data = observation(lane)
    for key in ("manual_publish_required", "send_button_automation_allowed", "note_id", "screen_url", "draft_saved", "save_readback", "edit_session"):
        data.pop(key)
    assert build_result(data)["ok"] is True
