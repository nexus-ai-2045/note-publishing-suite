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
    expected, _ = gate.read_workspace_settings(config, "article")
    return dict(schema_version=gate.SCHEMA, article_id="article", conversation_id="current",
                route="direct_draft", receipts=[], ssot_readback=expected, edit_plan={"toc": False}, **files,
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


@pytest.mark.parametrize("stage", sorted(gate.STAGES))
def test_reapproval_replaces_stale_receipts_without_mixing_history(packet, stage):
    assert approve(packet, stage)["status"] == "approved"
    old_receipts = list(packet["receipts"])
    Path(packet["draft"]).write_text("現版の本文", encoding="utf-8")
    assert gate.check_packet(packet, stage, "current")["status"] == "blocked"
    # 現版への承認を追加しても旧版receiptが混在していれば停止する。
    assert approve(packet, stage)["status"] == "blocked"
    packet["receipts"] = []
    assert approve(packet, stage)["status"] == "approved"
    packet["receipts"].extend(old_receipts)
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
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    command = [sys.executable, str(SCRIPT), "--packet", str(path), "--stage", "publish", "--conversation-id", "current", "--settings", str(tmp_path / "workspace-settings.json")]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["manual_publish_required"] is True
    assert {p: p.read_bytes() for p in tmp_path.iterdir()} == before
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
