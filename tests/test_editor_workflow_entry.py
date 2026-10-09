"""承認欠落・対象違いで外部CLIを起動しないことを検査する。"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from note_workflow_gate import check_packet, read_workspace_settings

spec = importlib.util.spec_from_file_location("editor_workflow_entry", SCRIPTS / "note_editor_apply.py")
editor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(editor)


def packet_file(tmp_path):
    for name in ("source", "draft", "proposal"):
        (tmp_path / name).write_text(name)
    (tmp_path / "style.md").write_text("テスト用文体")
    settings_path = tmp_path / "workspace-settings.json"
    settings_path.write_text(json.dumps({"schema_version": "nps-workspace-settings/v1", "workspace_root": ".",
        "storage": {"drafts": ".", "sources": ".", "feedback": "feedback"},
        "style": {"default_profile": "style.md", "article_profiles": {}}}))
    readback, _ = read_workspace_settings(settings_path, "nexample")
    packet = {
        "schema_version": "note-workflow-review/v1", "article_id": "nexample",
        "route": "direct_draft", "conversation_id": "current",
        "source_snapshot": "source", "draft": "draft", "proposed_draft": "proposal",
        "settings": {"account": "example"}, "ssot_readback": readback,
        "edit_plan": {"urls": [], "tags": [], "toc": True, "save": False}, "receipts": [],
    }
    from note_feedback import record_feedback
    _, dirs = read_workspace_settings(settings_path, "nexample")
    packet["feedback_readback"] = record_feedback(dirs, "nexample", tmp_path / "source", tmp_path / "draft",
                                                  tmp_path / "source", [], conversation_id="current")
    packet["layout"] = dict(toc=dict(decision="include", reason="見出し案内"),
                            footer_cards=dict(decision="omit", reason="不要", urls=[]))
    subjects = check_packet(packet, "edit", "current", tmp_path, settings_path=settings_path)["subject_hashes"]
    subject = subjects["edit"]
    packet["receipts"] = [{"stage": "edit", "article_id": "nexample", "conversation_id": "current",
                           "actor": "user", "status": "approved", "subject_sha256": subject,
                           "evidence_ref": "fixture-only", "observed_at": "2026-10-05T12:00:00+09:00"}]
    packet["receipts"].append(dict(stage="layout", article_id="nexample", conversation_id="current",
        actor="user", status="approved", subject_sha256=subjects["layout"],
        evidence_ref="fixture-only", observed_at="2026-10-05T12:00:00+09:00"))
    path = tmp_path / "review.json"
    path.write_text(json.dumps(packet))
    return path


@pytest.mark.parametrize("case", ["missing", "plan", "article", "account", "conversation", "settings", "readback", "missing_settings", "missing_source"])
def test_rejected_before_external_read(tmp_path, monkeypatch, capsys, case):
    path = packet_file(tmp_path)
    if case == "missing_source":
        (tmp_path / "source").unlink()
    args = ["apply", "--page", "fixture", "--expect-note-id", "nexample", "--expect-account", "example", "--toc", "--nps-settings", str(tmp_path / "workspace-settings.json")]
    if case != "missing":
        args += ["--workflow-packet", str(path), "--conversation-id", "wrong" if case == "conversation" else "current"]
    if case == "missing_settings":
        index = args.index("--nps-settings")
        del args[index:index + 2]
    if case == "settings":
        args[args.index(str(tmp_path / "workspace-settings.json"))] = str(tmp_path / "missing-settings.json")
    if case == "readback":
        packet = json.loads(path.read_text())
        packet["ssot_readback"] = {}
        path.write_text(json.dumps(packet))
    if case == "plan":
        args.append("--save")
    if case == "article":
        args[args.index("nexample")] = "nother"
    if case == "account":
        args[args.index("example")] = "other"
    def external_read(*args):
        pytest.fail("承認拒否後に外部CLIを起動した")
    monkeypatch.setattr(sys, "argv", args)
    monkeypatch.setattr(editor, "read_page_identity", external_read)
    assert editor.main() == 1
    assert json.loads(capsys.readouterr().out)["publication_actions_performed"] == []


def test_url_plan_is_not_reread_after_preflight(tmp_path, monkeypatch):
    path = packet_file(tmp_path)
    packet = json.loads(path.read_text())
    approved = "https://example.com/approved"
    urls_path = tmp_path / "urls.json"
    urls_path.write_text(json.dumps([approved]))
    packet["edit_plan"] = {"urls": [approved], "tags": [], "toc": False, "save": False}
    packet["layout"]["footer_cards"] = dict(decision="include", reason="参考", urls=[approved])
    subjects = check_packet(packet, "edit", "current", tmp_path, settings_path=tmp_path / "workspace-settings.json")["subject_hashes"]
    for receipt in packet["receipts"]:
        receipt["subject_sha256"] = subjects[receipt["stage"]]
    path.write_text(json.dumps(packet))
    def external_read(*args):
        urls_path.write_text(json.dumps(["https://example.com/not-approved"]))
        path.write_text("{}")
        return {"note_id": "nexample", "url": "https://editor.note.com/notes/nexample/edit/", "account": "example", "account_identity_verified": True,
                "account_identity_source": "authenticated_account_menu", "account_identity_id": "example"}
    seen = []
    def capture_embed(orca, page, url):
        seen.append(url)
        raise LookupError("fixture stop before actual write")
    monkeypatch.setattr(editor, "read_page_identity", external_read)
    monkeypatch.setattr(editor, "embed_url", capture_embed)
    monkeypatch.setattr(sys, "argv", ["apply", "--page", "fixture", "--expect-note-id", "nexample",
                                    "--expect-account", "example", "--urls-file", str(urls_path),
                                    "--workflow-packet", str(path), "--conversation-id", "current",
                                    "--nps-settings", str(tmp_path / "workspace-settings.json")])
    with pytest.raises(LookupError, match="fixture stop"):
        editor.main()
    assert seen == [approved]


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


def test_tag_candidate_changes_do_not_look_like_selection_changes(tag_readback):
    from note_editor_prepublish_verify import tag_operation_preflight
    tag_readback["current"]["suggested_tags"] = ["おすすめ", "AI"]
    assert tag_operation_preflight(tag_readback, "nexample", "example")["status"] == "approved"


@pytest.mark.parametrize("bad", [None, {}, {"baseline": None}, {"planned_additions": "AI"}])
def test_tag_preflight_invalid_observation_fails_closed(bad):
    from note_editor_prepublish_verify import tag_operation_preflight
    assert tag_operation_preflight(bad, "nexample", "example")["status"] == "blocked"
