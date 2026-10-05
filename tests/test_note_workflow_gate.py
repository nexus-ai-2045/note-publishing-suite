from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/note_workflow_gate.py"
spec = importlib.util.spec_from_file_location("note_workflow_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


@pytest.fixture
def packet(tmp_path, monkeypatch):
    files = {}
    for name in ("source_snapshot", "draft", "proposed_draft", "research_report"):
        path = tmp_path / (name + ".md")
        path.write_text(name, encoding="utf-8")
        files[name] = str(path)
    profile = tmp_path / "profile.md"
    profile.write_text("ユーザーの文体", encoding="utf-8")
    config = tmp_path / "workspace-settings.json"
    config.write_text(json.dumps(dict(schema_version="nps-workspace-settings/v1", workspace_root=".",
        storage=dict(drafts=".", sources=".", feedback="feedback"),
        style=dict(default_profile="profile.md", article_profiles={}))))
    original_check = gate.check_packet
    def configured_check(*args, **kwargs):
        kwargs.setdefault("settings_path", config)
        return original_check(*args, **kwargs)
    monkeypatch.setattr(gate, "check_packet", configured_check)
    expected, dirs = gate.read_workspace_settings(config, "article")
    sys.path.insert(0, str(SCRIPT.parent))
    from note_feedback import record_feedback
    feedback = record_feedback(dirs, "article", Path(files["source_snapshot"]), Path(files["draft"]),
                               Path(files["source_snapshot"]), [], conversation_id="current")
    return dict(schema_version=gate.SCHEMA, article_id="article", conversation_id="current",
                layout=dict(toc=dict(decision="include", reason="見出し案内"), footer_cards=dict(decision="omit", reason="今回は不要", urls=[])),
                route="direct_draft", receipts=[], ssot_readback=expected, feedback_readback=feedback, edit_plan={"toc": False}, **files,
                settings=dict(account="nexus_ai", tags=[], magazine=None, visibility="public",
                              article_type="free", price=0, sns_share=False, publish_mode="immediate",
                              schedule_at=None, image_rights_confirmed=True, cover_image=None))


def approve(packet, stage):
    result = gate.check_packet(packet, stage, "current")
    for item, sha in result["subject_hashes"].items():
        packet["receipts"].append(dict(article_id="article", conversation_id="current", stage=item,
                                       subject_sha256=sha, actor="user", status="approved",
                                       evidence_ref="runtime://receipt", observed_at="2026-10-05T10:00:00+09:00"))
    return gate.check_packet(packet, stage, "current")


@pytest.mark.parametrize("route", sorted(gate.ROUTES))
@pytest.mark.parametrize("stage", sorted(gate.STAGES))
def test_routes_approval_and_manual_boundary(packet, route, stage):
    packet["route"] = route
    assert gate.check_packet(packet, stage, "current")["status"] == "blocked"
    result = approve(packet, stage)
    assert result["status"] == "approved"
    assert result["automation_allowed"] is False
    assert result["manual_publish_required"] == (stage == "publish")


@pytest.mark.parametrize("stage,field", [("edit", "draft"), ("edit", "proposed_draft"),
    ("research", "research_report"), ("settings", "draft"), ("publish", "draft"),
    ("publish", "research_report"), ("edit", "source_snapshot"), ("research", "source_snapshot"),
    ("settings", "source_snapshot"), ("publish", "source_snapshot")])
def test_stale_content(packet, stage, field):
    approve(packet, stage)
    Path(packet[field]).write_text("変更", encoding="utf-8")
    assert gate.check_packet(packet, stage, "current")["status"] == "blocked"


@pytest.mark.parametrize("field,value", [("article_id", "other"), ("conversation_id", "old"),
    ("actor", "assistant"), ("status", "pending"), ("evidence_ref", ""),
    ("observed_at", "2026-10-05T10:00:00")])
def test_bad_receipt(packet, field, value):
    approve(packet, "publish")
    packet["receipts"][0][field] = value
    assert gate.check_packet(packet, "publish", "current")["status"] == "blocked"


def test_changed_settings_and_edit_plan(packet):
    approve(packet, "settings")
    packet["settings"]["tags"] = ["AI"]
    assert gate.check_packet(packet, "settings", "current")["status"] == "blocked"
    approve(packet, "edit")
    packet["edit_plan"]["toc"] = True
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


@pytest.mark.parametrize("stage", sorted(gate.STAGES))
def test_missing_source(packet, stage):
    approve(packet, stage)
    Path(packet["source_snapshot"]).unlink()
    assert gate.check_packet(packet, stage, "current")["status"] == "blocked"


@pytest.mark.parametrize("settings", [{}, None, {"publish_mode": []}])
def test_bad_settings(packet, settings):
    packet["settings"] = settings
    assert gate.check_packet(packet, "settings", "current")["status"] == "blocked"


@pytest.mark.parametrize("key,value", [("price", -1), ("price", True), ("image_rights_confirmed", False),
    ("sns_share", "yes"), ("tags", "AI"), ("publish_mode", []), ("article_type", "paid")])
def test_settings_validation(packet, key, value):
    packet["settings"][key] = value
    assert gate.check_packet(packet, "settings", "current")["status"] == "blocked"


def test_schedule_timezone(packet):
    packet["settings"].update(publish_mode="scheduled", schedule_at="2026-10-10T10:00:00")
    assert gate.check_packet(packet, "settings", "current")["status"] == "blocked"
    packet["settings"]["schedule_at"] += "+09:00"
    assert approve(packet, "settings")["status"] == "approved"


def test_empty_research(packet):
    Path(packet["research_report"]).write_text(" \n")
    assert gate.check_packet(packet, "research", "current")["status"] == "blocked"


def test_cli_read_only_and_bad_json(packet, tmp_path):
    approve(packet, "publish")
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(packet))
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    command = [sys.executable, str(SCRIPT), "--packet", str(path), "--stage", "publish", "--conversation-id", "current", "--settings", str(tmp_path / "workspace-settings.json")]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["manual_publish_required"] is True
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
    path.write_text("{bad")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "blocked"


@pytest.mark.parametrize("bad", [None, [], {}, {"route": []}, {"receipts": [None]}])
def test_malformed_packet(bad):
    assert gate.check_packet(bad, "edit", "current")["status"] == "blocked"


@pytest.mark.parametrize("text", ['{"route":"direct_draft","route":"source_article"}', '{"price":NaN}', 'null'])
def test_loader_rejects_malformed(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text)
    assert gate.load_and_check(path, "edit", "current", settings_path=tmp_path / "workspace-settings.json")["status"] == "blocked"


def test_loader_relative_paths(packet, tmp_path):
    approve(packet, "edit")
    for key in ("source_snapshot", "draft", "proposed_draft", "research_report"):
        packet[key] = Path(packet[key]).name
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(packet))
    assert gate.load_and_check(path, "edit", "current", settings_path=tmp_path / "workspace-settings.json")["status"] == "approved"


@pytest.mark.parametrize("field,stage", [("source_snapshot", "edit"), ("draft", "edit"), ("proposed_draft", "edit"), ("source_snapshot", "research"), ("draft", "publish")])
def test_empty_content_blocks(packet, field, stage):
    Path(packet[field]).write_text(" \n")
    assert gate.check_packet(packet, stage, "current")["status"] == "blocked"


@pytest.mark.parametrize("field", ["draft", "proposed_draft"])
def test_source_cannot_be_draft(packet, field):
    packet[field] = packet["source_snapshot"]
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


def test_source_symlink_cannot_be_draft(packet, tmp_path):
    linked = tmp_path / "linked.md"
    linked.symlink_to(packet["source_snapshot"])
    packet["draft"] = str(linked)
    assert gate.check_packet(packet, "research", "current")["status"] == "blocked"


@pytest.mark.parametrize("stage", ["settings", "publish"])
def test_cover_bytes_bound_to_approval(packet, tmp_path, stage):
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"first image")
    packet["settings"]["cover_image"] = cover.name
    before = gate.check_packet(packet, stage, "current", tmp_path)
    for item, sha in before["subject_hashes"].items():
        packet["receipts"].append(dict(article_id="article", conversation_id="current", stage=item,
                                      subject_sha256=sha, actor="user", status="approved",
                                      evidence_ref="runtime://receipt", observed_at="2026-10-05T10:00:00+09:00"))
    assert gate.check_packet(packet, stage, "current", tmp_path)["status"] == "approved"
    cover.write_bytes(b"replacement image")
    assert gate.check_packet(packet, stage, "current", tmp_path)["status"] == "blocked"


@pytest.mark.parametrize("exists", [False, True])
def test_missing_or_empty_cover_blocks(packet, tmp_path, exists):
    cover = tmp_path / "cover.png"
    if exists:
        cover.write_bytes(b"")
    packet["settings"]["cover_image"] = str(cover)
    assert gate.check_packet(packet, "settings", "current")["status"] == "blocked"


@pytest.mark.parametrize("visibility", ["garbage", "private", "limited", "PUBLIC", ""])
def test_unknown_visibility_fails_closed(packet, visibility):
    packet["settings"]["visibility"] = visibility
    assert gate.check_packet(packet, "settings", "current")["status"] == "blocked"
    assert gate.check_packet(packet, "publish", "current")["status"] == "blocked"


def test_edit_account_change_invalidates(packet):
    assert approve(packet, "edit")["status"] == "approved"
    packet["settings"]["account"] = "another-account"
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


@pytest.mark.parametrize("settings", [None, {}, {"account": ""}, {"account": False}])
def test_edit_account_required(packet, settings):
    packet["settings"] = settings
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


@pytest.mark.parametrize("content", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{bad'])
def test_load_packet_rejects_invalid_json(tmp_path, content):
    path = tmp_path / "packet.json"
    path.write_text(content)
    with pytest.raises(ValueError):
        gate.load_packet(path)


@pytest.mark.parametrize("stage", sorted(gate.STAGES))
def test_external_settings_required(packet, stage):
    assert gate.check_packet(packet, stage, "current", settings_path=None)["status"] == "blocked"


@pytest.mark.parametrize("stage", sorted(gate.STAGES))
def test_every_use_reads_profile_and_invalidates_approval(packet, tmp_path, stage):
    assert approve(packet, stage)["status"] == "approved"
    (tmp_path / "profile.md").write_text("変更された文体", encoding="utf-8")
    result = gate.check_packet(packet, stage, "current")
    assert result["status"] == "blocked"
    assert result["expected_readback"] != packet["ssot_readback"]
    packet["ssot_readback"] = result["expected_readback"]
    assert gate.check_packet(packet, stage, "current")["status"] == "blocked"


@pytest.mark.parametrize("stage", sorted(gate.STAGES))
def test_settings_bytes_change_invalidates_approval(packet, tmp_path, stage):
    approve(packet, stage)
    path = tmp_path / "workspace-settings.json"
    path.write_text(path.read_text() + "\n")
    result = gate.check_packet(packet, stage, "current")
    assert result["status"] == "blocked"
    packet["ssot_readback"] = result["expected_readback"]
    assert gate.check_packet(packet, stage, "current")["status"] == "blocked"


@pytest.mark.parametrize("readback", [None, {}, {"settings_sha256": "fake", "reference_hashes": {}}])
def test_missing_or_wrong_readback_blocks(packet, readback):
    packet["ssot_readback"] = readback
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


@pytest.mark.parametrize("key", ["settings_path", "nps_settings", "workspace_settings"])
def test_packet_cannot_override_external_settings(packet, key):
    packet[key] = "/fake/settings.json"
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


def test_article_profile_readback(packet, tmp_path):
    config_path = tmp_path / "workspace-settings.json"
    profile = tmp_path / "article-style.md"
    profile.write_text("記事ごとの文体")
    config = gate.load_packet(config_path)
    config["style"]["article_profiles"]["article"] = [profile.name]
    config_path.write_text(json.dumps(config))
    expected, _ = gate.read_workspace_settings(config_path, "article")
    assert str(profile.resolve()) in expected["reference_hashes"]
    packet["ssot_readback"] = expected
    assert approve(packet, "edit")["status"] == "approved"
    profile.write_text("記事ごとの文体更新")
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


@pytest.mark.parametrize("key,value", [("schema_version", "wrong"), ("workspace_root", None), ("storage", {}), ("style", {})])
def test_bad_workspace_config(packet, tmp_path, key, value):
    config_path = tmp_path / "workspace-settings.json"
    config = gate.load_packet(config_path)
    config[key] = value
    config_path.write_text(json.dumps(config))
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


@pytest.mark.parametrize("target", ["profile", "drafts", "sources", "feedback", "workspace"])
def test_package_paths_rejected(packet, tmp_path, target):
    config_path = tmp_path / "workspace-settings.json"
    config = gate.load_packet(config_path)
    if target == "profile":
        config["style"]["default_profile"] = str(SCRIPT)
    elif target == "workspace":
        config["workspace_root"] = str(SCRIPT.parent)
    else:
        config["storage"][target] = str(SCRIPT.parent)
    config_path.write_text(json.dumps(config))
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


def test_package_config_rejected(packet):
    assert gate.check_packet(packet, "edit", "current", settings_path=SCRIPT)["status"] == "blocked"


@pytest.mark.parametrize("field", ["source_snapshot", "draft", "proposed_draft"])
def test_actual_storage_containment(packet, tmp_path, field):
    config_path = tmp_path / "workspace-settings.json"
    config = gate.load_packet(config_path)
    key = "sources" if field == "source_snapshot" else "drafts"
    config["storage"][key] = "not-containing-current-files"
    config_path.write_text(json.dumps(config))
    packet["ssot_readback"], _ = gate.read_workspace_settings(config_path, "article")
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


def test_missing_profile_fails_closed(packet, tmp_path):
    (tmp_path / "profile.md").unlink()
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


@pytest.mark.parametrize("stage", ["layout", "settings", "publish"])
@pytest.mark.parametrize("layout", [None, {}, {"toc": {"decision": "omit", "reason": ""}},
    {"toc": {"decision": "omit", "reason": "短文"}, "footer_cards": {"decision": "include", "reason": "参照", "urls": []}},
    {"toc": {"decision": "omit", "reason": "短文"}, "footer_cards": {"decision": "omit", "reason": "不要", "urls": ["https://example.com/"]}}])
def test_layout_missing_or_invalid_blocks(packet, stage, layout):
    packet["layout"] = layout
    assert approve(packet, stage)["status"] == "blocked"


@pytest.mark.parametrize("stage", ["layout", "settings", "publish"])
def test_layout_changed_choice_invalidates(packet, stage):
    assert approve(packet, stage)["status"] == "approved"
    packet["layout"]["toc"]["decision"] = "omit"
    assert gate.check_packet(packet, stage, "current")["status"] == "blocked"


@pytest.mark.parametrize("urls", [["ftp://example.com"], ["https://example.com", "https://example.com"], ["https://"], [4]])
def test_bad_card_urls_block(packet, urls):
    packet["layout"]["footer_cards"] = dict(decision="include", reason="参照", urls=urls)
    assert approve(packet, "layout")["status"] == "blocked"


def test_footer_url_change_invalidates_layout(packet):
    packet["layout"]["footer_cards"] = dict(decision="include", reason="参照", urls=["https://example.com/a"])
    assert approve(packet, "layout")["status"] == "approved"
    packet["layout"]["footer_cards"]["urls"] = ["https://example.com/b"]
    assert gate.check_packet(packet, "layout", "current")["status"] == "blocked"


def test_text_edit_before_layout_decision_allowed(packet):
    packet.pop("layout")
    assert approve(packet, "edit")["status"] == "approved"


@pytest.mark.parametrize("plan", [{"toc": True}, {"footer_embed_urls": ["https://example.com"]}])
def test_layout_edit_needs_separate_layout_receipt(packet, plan):
    packet["edit_plan"] = plan
    if plan.get("footer_embed_urls"):
        packet["layout"]["footer_cards"] = dict(decision="include", reason="参照", urls=plan["footer_embed_urls"])
    result = approve(packet, "edit")
    assert result["status"] == "approved"
    packet["receipts"] = [r for r in packet["receipts"] if r["stage"] == "edit"]
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


@pytest.mark.parametrize("field,value", [("article_id", "other"), ("conversation_id", "other")])
def test_layout_other_identity_blocks(packet, field, value):
    approve(packet, "layout")
    packet["receipts"][0][field] = value
    assert gate.check_packet(packet, "layout", "current")["status"] == "blocked"


def test_cli_urls_plan_requires_layout_approval(packet):
    packet["edit_plan"] = dict(urls=["https://example.com"], toc=False)
    assert approve(packet, "edit")["status"] == "blocked"
    packet["layout"]["footer_cards"] = dict(decision="include", reason="参照", urls=["https://example.com"])
    packet["receipts"] = []
    assert approve(packet, "edit")["status"] == "approved"
    packet["receipts"] = [r for r in packet["receipts"] if r["stage"] != "layout"]
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


@pytest.mark.parametrize("stage", sorted(gate.STAGES))
def test_missing_feedback_blocks_every_stage(packet, tmp_path, stage):
    (tmp_path / "feedback/article/feedback.json").unlink()
    assert gate.check_packet(packet, stage, "current")["status"] == "blocked"


@pytest.mark.parametrize("stage", sorted(gate.STAGES))
def test_updated_learning_invalidates_receipts(packet, tmp_path, stage):
    assert approve(packet, stage)["status"] == "approved"
    from note_feedback import record_feedback
    _, dirs = gate.read_workspace_settings(tmp_path / "workspace-settings.json", "article")
    packet["feedback_readback"] = record_feedback(dirs, "article", Path(packet["source_snapshot"]),
        Path(packet["draft"]), Path(packet["source_snapshot"]),
        [dict(origin="ai", decision="rejected", before="draft", after="短縮案",
              reason="本人原文を維持", evidence_ref="fixture://human")], conversation_id="current")
    assert gate.check_packet(packet, stage, "current")["status"] == "blocked"


def test_new_author_edit_requires_feedback_refresh(packet):
    approve(packet, "edit")
    Path(packet["draft"]).write_text("新しい本人追記")
    result = gate.check_packet(packet, "edit", "current")
    assert result["status"] == "blocked"
    assert any("feedback" in reason for reason in result["reasons"])


def test_feedback_readback_not_self_attested(packet):
    packet["feedback_readback"] = {}
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


def test_gate_list_current_approval_does_not_reask(packet):
    approve(packet, "settings")
    rows = {r["stage"]: r for r in gate.list_gates(packet, "current", settings_path=Path(packet["draft"]).parent / "workspace-settings.json")["gates"]}
    assert rows["settings"]["approval_status"] == "approved"
    assert rows["settings"]["status"] == "approved"
    assert "次工程" in rows["settings"]["next_action"]
    assert rows["settings"]["evidence_refs"] == ["runtime://receipt"]
    assert rows["research"]["approval_status"] == "pending"


@pytest.mark.parametrize("field,value,reason", [
    ("article_id", "other", "別記事"), ("conversation_id", "other", "別会話"),
    ("subject_sha256", "old", "承認対象の版が変更"), ("status", "pending", "未承認"),
])
def test_gate_list_receipt_failure_reason(packet, field, value, reason):
    approve(packet, "research")
    packet["receipts"][0][field] = value
    row = next(r for r in gate.list_gates(packet, "current", settings_path=Path(packet["draft"]).parent / "workspace-settings.json")["gates"] if r["stage"] == "research")
    assert row["approval_status"] == "invalidated"
    assert reason in row["invalidation_reasons"]
    assert row["status"] == "blocked"


def test_gate_list_dependency_failure_keeps_current_stage_approval(packet):
    approve(packet, "settings")
    packet["receipts"] = [r for r in packet["receipts"] if r["stage"] == "settings"]
    row = next(r for r in gate.list_gates(packet, "current", settings_path=Path(packet["draft"]).parent / "workspace-settings.json")["gates"] if r["stage"] == "settings")
    assert row["approval_status"] == "approved"
    assert row["status"] == "blocked"
    assert "再確認質問は不要" in row["next_action"]


def test_gate_list_stale_settings_keeps_old_receipt_and_checker_semantics(packet):
    approve(packet, "settings")
    before = list(packet["receipts"])
    packet["settings"]["tags"] = ["AI"]
    result = gate.list_gates(packet, "current", settings_path=Path(packet["draft"]).parent / "workspace-settings.json")
    row = next(r for r in result["gates"] if r["stage"] == "settings")
    assert row["approval_status"] == "invalidated"
    assert packet["receipts"] == before
    assert result["automation_allowed"] is False
    assert result["manual_publish_required"] is True


def test_gate_list_cli_read_only_bad_json(packet, tmp_path):
    path = tmp_path / "review.json"
    path.write_text(json.dumps(packet))
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    command = [sys.executable, str(SCRIPT), "--packet", str(path), "--list-gates",
               "--conversation-id", "current", "--settings", str(tmp_path / "workspace-settings.json")]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert len(json.loads(result.stdout)["gates"]) == 5
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
    path.write_text('{"receipts":[],"receipts":[]}')
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert all(r["approval_status"] == "unavailable" for r in json.loads(result.stdout)["gates"])
