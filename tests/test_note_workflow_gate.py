from __future__ import annotations

import importlib.util
import copy
import json
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/note_workflow_gate.py"
spec = importlib.util.spec_from_file_location("note_workflow_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


@pytest.mark.parametrize('entry', ['note_workflow_gate.py', 'pre_publish_check.py'])
@pytest.mark.parametrize('ambient', ['empty', 'foreign', 'spoofed'])
def test_standalone_sibling_loading_in_fresh_process(entry, ambient):
    code = '''
import importlib.util, json, sys, tempfile, types
from pathlib import Path
script = Path(sys.argv[1])
sys.path.insert(0, str(script.parent.parent))
assert str(script.parent) not in sys.path
assert 'note_feedback' not in sys.modules
if sys.argv[2] != 'empty':
    wrong = types.ModuleType('note_feedback')
    wrong.__file__ = str(script.with_name('note_feedback.py') if sys.argv[2] == 'spoofed'
                         else script.parent.parent / 'other-repo/note_feedback.py')
    def foreign_helper(*args, **kwargs):
        raise AssertionError('foreign helper must not be used')
    wrong.InputCapture = tuple
    wrong.check_input_capture = wrong.remember_input_bytes = wrong.remember_input_path = foreign_helper
    sys.modules['note_feedback'] = wrong
spec = importlib.util.spec_from_file_location('standalone_entry', script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if sys.argv[2] == 'empty':
    assert 'note_feedback' not in sys.modules
else:
    assert sys.modules['note_feedback'] is wrong
feedback = module._load_sibling_module('note_feedback')
assert Path(feedback.__file__).resolve() == script.with_name('note_feedback.py').resolve()
assert Path(feedback.check_input_capture.__code__.co_filename).resolve() == script.with_name('note_feedback.py').resolve()
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    voice = root / 'voice.md'
    voice.write_text('Author wording.', encoding='utf-8')
    settings = root / 'settings.json'
    settings.write_text(json.dumps(dict(schema_version='nps-workspace-settings/v1', workspace_root='.',
        storage=dict(drafts='drafts', sources='sources', feedback='feedback'),
        style=dict(default_profile=voice.name, article_profiles={'article':[voice.name]},
                   history_learning_policy=dict(schema='nps-history-learning-policy/v1', required=True)))), encoding='utf-8')
    expected, dirs = module.read_workspace_settings(settings, 'article')
    assert expected['history_learning_policy']['required'] is True
    assert set(dirs) == {'drafts','sources','feedback'}
    assert str(script.parent) not in sys.path
print('standalone-readback-ok')
'''
    checked = subprocess.run([sys.executable, '-I', '-c', code, str(SCRIPT.with_name(entry)), ambient],
                             capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stderr
    assert checked.stdout.strip() == 'standalone-readback-ok'


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
    value = dict(schema_version=gate.SCHEMA, article_id="article", conversation_id="current",
                layout=dict(cover=dict(decision="omit", reason="本文中心の構成として本人が採用"), toc=dict(decision="include", reason="見出し案内"), footer_cards=dict(decision="omit", reason="今回は不要", urls=[]), illustrations=dict(decision="omit", reason="本文で十分", items=[]), embeds=dict(decision="omit", reason="不要", items=[]), review=dict(proposal_ref="conversation://proposal", discussion_ref="conversation://discussion", decision_ref="conversation://decision")),
                route="direct_draft", receipts=[], ssot_readback=expected, feedback_readback=feedback, edit_plan={"toc": False}, **files,
                settings=dict(account="nexus-ai-2045", tags=[], magazine=None, visibility="public",
                              article_type="free", price=0, sns_share=False, publish_mode="immediate",
                              schedule_at=None, image_rights_confirmed=True, cover_image=None))
    value["layout"]["hyperlinks"] = dict(decision="omit", reason="このfixtureでは本文リンクなし", items=[])
    chosen = ["AI", "研究", "ニュース", "技術", "観測連載"]
    value["settings"]["tags"] = chosen
    value["tag_design"] = dict(schema="note-tag-design/v1", article_id="article",
        body_sha256=hashlib.sha256(b"draft").hexdigest(),
        policy=dict(id="nps-local-tags/v1", min_tags=5, max_tags=10),
        strategy={axis: dict(reason="選定時に本文・読者導線・発信方針を照合", evidence_ref=f"review://tags/{axis}")
                  for axis in ("content", "discovery", "branding")},
        tags=[dict(tag=tag, role=role, reason="本文の話題に対応", evidence_ref="draft://topic")
              for tag, role in zip(chosen, ["topic", "topic", "context", "context", "series"])],
        previous_article=dict(article_id="previous", reference="previous.md#tags", tags=["AI"],
                              comparison="前話の主題を維持し今回の文脈を追加"))
    selected = dict(article_id="article", account="nexus-ai-2045", selected_tags=list(chosen),
                    suggested_tags=[], selection_scope_verified=True)
    value["tag_preflight"] = dict(baseline=dict(selected), current=dict(selected), planned_additions=chosen)
    return value


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
    packet["layout"]["cover"] = dict(decision="include", reason="本人採用のタイトル画")
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


@pytest.fixture
def quality_packet(packet, tmp_path):
    from datetime import datetime, timedelta, timezone
    import hashlib
    from note_feedback import record_feedback
    settings = tmp_path / "workspace-settings.json"
    config = json.loads(settings.read_text())
    config["research_quality_policy"] = {
        "schema_version": "nps-research-quality-policy/v1", "required": True,
        "max_age_days": {"dynamic": 7, "official": 30, "creator": 30}}
    settings.write_text(json.dumps(config))
    packet["ssot_readback"], dirs = gate.read_workspace_settings(settings, "article")
    evidence = tmp_path / "observation.md"
    evidence.write_text("公式本文の保存と読み合わせ結果")
    loops = ["article_local", "immediate_publication", "article_outcomes", "topic_portfolio", "strategy"]
    entries = [dict(origin="ai", decision="pending", before="", after="測定予定",
                    reason="公開後に判断", evidence_ref=f"quality:{scope}") for scope in loops]
    packet["feedback_readback"] = record_feedback(dirs, "article", Path(packet["source_snapshot"]),
        Path(packet["draft"]), Path(packet["source_snapshot"]), entries, conversation_id="current")
    report = dict(schema_version="note-research-quality/v1", article_id="article", topic="今回の主題",
        sources=[dict(id="source-1", kind="official", url="https://example.com/guidance",
            observed_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            evidence_path="observation.md", evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
            readback="本文を読み合わせた結果", reuse=None)],
        areas={key: dict(status="pass", reason="今回の本文との照合結果", decision="提案として確認",
                         source_ids=["source-1"], unresolved=[])
               for key in ["seo", "aio", "note", "tags", "pdca", "creator_trends"]},
        pdca_loops=[dict(scope=scope, owner="記事の担当者", change="見出しの調整", measure="読者の反応",
            when="公開後に確認", status="planned", missing_data=["公開後の実測"], constraints=["因果は未確認"],
            feedback_entry_ref=f"quality:{scope}") for scope in loops])
    Path(packet["research_report"]).write_text(json.dumps(report))
    return packet


def quality_report(packet, mutate):
    path = Path(packet["research_report"])
    report = json.loads(path.read_text())
    mutate(report)
    path.write_text(json.dumps(report))


def test_quality_policy_blocks_legacy_markdown(packet, tmp_path):
    settings = tmp_path / "workspace-settings.json"
    config = json.loads(settings.read_text())
    config["research_quality_policy"] = {"schema_version": "nps-research-quality-policy/v1", "required": True,
        "max_age_days": {"dynamic": 7, "official": 30, "creator": 30}}
    settings.write_text(json.dumps(config))
    packet["ssot_readback"], _ = gate.read_workspace_settings(settings, "article")
    assert approve(packet, "research")["status"] == "blocked"


def test_quality_complete_plan_allows_prepublication(quality_packet):
    assert approve(quality_packet, "publish")["status"] == "approved"


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(schema_version="other"),
    lambda r: r.update(article_id="other"),
    lambda r: r["areas"].pop("seo"),
    lambda r: r["areas"]["tags"].update(status="unknown"),
    lambda r: r["areas"]["aio"].update(unresolved=["必須主張の確認待ち"]),
    lambda r: r["areas"]["seo"].update(source_ids=["missing"]),
    lambda r: r["sources"][0].pop("observed_at"),
    lambda r: r["sources"][0].update(observed_at="2099-01-01T00:00:00+00:00"),
    lambda r: r["sources"][0].update(observed_at="2020-01-01T00:00:00+00:00"),
    lambda r: r["sources"][0].update(observed_at="2026-10-09T00:00:00"),
    lambda r: r["sources"][0].update(evidence_sha256="0" * 64),
    lambda r: r["sources"][0].update(readback=""),
    lambda r: r["sources"][0].update(kind="other"),
    lambda r: r["sources"][0].update(reuse={"topic": "別主題", "unchanged": True, "reason": "再利用"}),
    lambda r: r["sources"][0].update(reuse={"topic": "今回の主題", "unchanged": False, "reason": "変更あり"}),
    lambda r: r["sources"][0].update(reuse={"topic": "今回の主題", "unchanged": True, "reason": ""}),
    lambda r: r["pdca_loops"].pop(),
    lambda r: r["pdca_loops"][0].update(owner=""),
    lambda r: r["pdca_loops"][0].update(feedback_entry_ref="unrecorded"),
    lambda r: r["pdca_loops"][0].update(status="observed"),
])
def test_quality_incomplete_evidence_blocks_even_with_receipt(quality_packet, mutation):
    quality_report(quality_packet, mutation)
    assert approve(quality_packet, "research")["status"] == "blocked"


def test_quality_reasoned_na_and_fresh_reuse(quality_packet):
    def mutate(r):
        r["areas"]["creator_trends"].update(status="not_applicable", reason="比較対象のない本人の日記", source_ids=[])
        r["sources"][0]["reuse"] = dict(topic=r["topic"], unchanged=True, reason="同テーマで仕様変更なし")
    quality_report(quality_packet, mutate)
    assert approve(quality_packet, "research")["status"] == "approved"
    quality_report(quality_packet, lambda r: r["areas"]["creator_trends"].update(reason=""))
    assert approve(quality_packet, "research")["status"] == "blocked"


@pytest.mark.parametrize("target", ["report", "evidence", "policy"])
def test_quality_subject_invalidates(quality_packet, tmp_path, target):
    assert approve(quality_packet, "research")["status"] == "approved"
    if target == "report":
        quality_report(quality_packet, lambda r: r["areas"]["seo"].update(reason="再確認した結果"))
    elif target == "evidence":
        (tmp_path / "observation.md").write_text("保存資料が変更された")
    else:
        settings = tmp_path / "workspace-settings.json"
        config = json.loads(settings.read_text())
        config["research_quality_policy"]["max_age_days"]["official"] = 10
        settings.write_text(json.dumps(config))
        quality_packet["ssot_readback"], _ = gate.read_workspace_settings(settings, "article")
    assert gate.check_packet(quality_packet, "research", "current")["status"] == "blocked"


def test_quality_cli_qa_entry(quality_packet, tmp_path):
    approve(quality_packet, "research")
    path = tmp_path / "review.json"
    path.write_text(json.dumps(quality_packet))
    command = [sys.executable, str(SCRIPT), "--settings", str(tmp_path / "workspace-settings.json"),
               "--packet", str(path), "--stage", "research", "--conversation-id", "current"]
    assert subprocess.run(command, capture_output=True, text=True).returncode == 0
    quality_report(quality_packet, lambda r: r["areas"].pop("note"))
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "blocked"


@pytest.mark.parametrize("policy", [None, {}, {"required": True},
    {"schema_version": "nps-research-quality-policy/v1", "required": "true", "max_age_days": {"dynamic": 7, "official": 30, "creator": 30}},
    {"schema_version": "nps-research-quality-policy/v1", "required": True, "max_age_days": {"dynamic": 0, "official": 30, "creator": 30}}])
def test_invalid_quality_policy_fails_closed(packet, tmp_path, policy):
    settings = tmp_path / "workspace-settings.json"
    config = json.loads(settings.read_text())
    config["research_quality_policy"] = policy
    settings.write_text(json.dumps(config))
    assert gate.check_packet(packet, "research", "current")["status"] == "blocked"


def test_explicit_quality_disabled_keeps_legacy(packet, tmp_path):
    settings = tmp_path / "workspace-settings.json"
    config = json.loads(settings.read_text())
    config["research_quality_policy"] = {"schema_version": "nps-research-quality-policy/v1", "required": False,
        "max_age_days": {"dynamic": 7, "official": 30, "creator": 30}}
    settings.write_text(json.dumps(config))
    packet["ssot_readback"], _ = gate.read_workspace_settings(settings, "article")
    assert approve(packet, "research")["status"] == "approved"


@pytest.mark.parametrize("raw", ['{broken', '[]', '{"schema_version": 1, "schema_version": 2}', '{"x": NaN}'])
def test_malformed_quality_json_blocks(quality_packet, raw):
    Path(quality_packet["research_report"]).write_text(raw)
    assert approve(quality_packet, "research")["status"] == "blocked"


def test_quality_ages_use_kind_and_clock(quality_packet, tmp_path):
    from datetime import datetime, timedelta, timezone
    from note_research_quality import check_quality_report
    policy = quality_packet["ssot_readback"]["research_quality_policy"]
    report = json.loads(Path(quality_packet["research_report"]).read_text())
    now = datetime(2026, 10, 9, tzinfo=timezone.utc)
    report["sources"][0]["observed_at"] = (now - timedelta(days=7)).isoformat()
    report["sources"][0]["kind"] = "dynamic"
    refs = {loop["feedback_entry_ref"] for loop in report["pdca_loops"]}
    kwargs = dict(article_id="article", base_dir=tmp_path, feedback_refs=refs)
    assert check_quality_report(json.dumps(report), policy, now=now, **kwargs)
    with pytest.raises(ValueError, match="鮮度切れ"):
        check_quality_report(json.dumps(report), policy, now=now + timedelta(microseconds=1), **kwargs)
    report["sources"][0]["kind"] = "official"
    assert check_quality_report(json.dumps(report), policy, now=now + timedelta(days=1), **kwargs)


def test_quality_invalid_feedback_blocks_without_crash(quality_packet, tmp_path):
    path = tmp_path / "feedback/article/feedback.json"
    record = json.loads(path.read_text())
    record["snapshot_hashes"]["draft"] = "0" * 64
    path.write_text(json.dumps(record))
    assert gate.check_packet(quality_packet, "research", "current")["status"] == "blocked"


@pytest.mark.parametrize("url", ["https://:", "https://@/", "https://example.com:99999/path", "https://example.com:invalid/path"])
def test_quality_invalid_source_url_rejected(quality_packet, url):
    quality_report(quality_packet, lambda r: r["sources"][0].update(url=url))
    assert approve(quality_packet, "research")["status"] == "blocked"


@pytest.mark.parametrize("url", ["https://note.com/公式/記事?q=生成AI&sort=新着#本文", "https://例え.テスト/資料?主題=文章", "https://example.com:443/guidance?q=writing%20quality"])
def test_quality_valid_unicode_and_query_source_url(quality_packet, url):
    quality_report(quality_packet, lambda r: r["sources"][0].update(url=url))
    assert approve(quality_packet, "research")["status"] == "approved"


@pytest.mark.parametrize("url", ["https://user:password@example.com/path", "https://user@example.com/path", "https://example.com/\x00path", "https://example.com/\x7fpath", "https://example.com/\tpath"])
def test_quality_source_url_credentials_and_controls_rejected(quality_packet, url):
    quality_report(quality_packet, lambda r: r["sources"][0].update(url=url))
    assert approve(quality_packet, "research")["status"] == "blocked"


def test_image_subject_hash_is_stable_across_single_and_aggregate_stages(packet, monkeypatch):
    import image_reference_gate
    monkeypatch.setattr(image_reference_gate, "check_settings", lambda *args, **kwargs: {
        "status": "ok", "errors": [], "hashes": {"output": "1" * 64, "receipt": "2" * 64}})
    for stage in ("edit", "research", "layout", "settings", "publish"):
        result = approve(packet, stage)
        assert result["status"] == "approved", (stage, result["reasons"])


def test_object_article_profile_preserves_style_reference_contract(tmp_path):
    (tmp_path/'voice.md').write_text('voice')
    settings = tmp_path/'settings.json'
    settings.write_text(json.dumps({'schema_version':'nps-workspace-settings/v1','workspace_root':'.','storage':{'drafts':'.','sources':'.','feedback':'.'},'style':{'default_profile':'voice.md','article_profiles':{'target':{'references':['voice.md'],'image_reference_policy':'policy.json','image_reference_receipt':'image.json'},'legacy':['voice.md']}}}))
    current,_ = gate.read_workspace_settings(settings,'target')
    legacy,_ = gate.read_workspace_settings(settings,'legacy')
    assert current['reference_hashes']==legacy['reference_hashes']


@pytest.mark.parametrize("stage", ["settings", "publish"])
@pytest.mark.parametrize("problem", ["missing", "body", "reason", "duplicate", "previous"])
def test_tag_design_blocks_settings_and_publish(packet, stage, problem):
    if problem == "missing": packet.pop("tag_design")
    elif problem == "body": packet["tag_design"]["body_sha256"] = "0" * 64
    elif problem == "reason": packet["tag_design"]["tags"][0]["reason"] = ""
    elif problem == "duplicate": packet["tag_design"]["tags"][1]["tag"] = "#AI"
    elif problem == "previous": packet["tag_design"].pop("previous_article")
    result = approve(packet, stage)
    assert result["status"] == "blocked"
    assert any("tag_design" in reason for reason in result["reasons"])


def test_tag_design_does_not_change_edit_stage(packet):
    packet.pop("tag_design")
    packet.pop("tag_preflight")
    packet["settings"]["tags"] = []
    assert approve(packet, "edit")["status"] == "approved"


def test_tag_candidates_are_not_selected_at_publish(packet):
    for snapshot in packet["tag_preflight"]["baseline"], packet["tag_preflight"]["current"]:
        snapshot["selected_tags"] = []
        snapshot["suggested_tags"] = packet["settings"]["tags"]
    assert approve(packet, "settings")["status"] == "approved"
    result = approve(packet, "publish")
    assert result["status"] == "blocked"
    assert "tag_selection: tag_selected_design_mismatch" in result["reasons"]


@pytest.mark.parametrize("changed", ["tag_reason", "strategy"])
def test_publish_requires_actual_selected_region_and_invalidates_changed_design(packet, changed):
    assert approve(packet, "publish")["status"] == "approved"
    if changed == "strategy":
        packet["tag_design"]["strategy"]["discovery"]["reason"] = "読者の検索意図を再確認した選定理由"
    else:
        packet["tag_design"]["tags"][0]["reason"] = "選定理由を変更"
    assert gate.check_packet(packet, "publish", "current")["status"] == "blocked"
    packet["receipts"] = []
    assert approve(packet, "publish")["status"] == "approved"
    packet["tag_preflight"]["current"]["selection_scope_verified"] = False
    assert approve(packet, "publish")["status"] == "blocked"


def test_publish_post_edit_keeps_baseline_and_binds_authorized_transition(packet):
    tags = list(packet['settings']['tags'])
    before = packet['tag_preflight']['baseline']
    before['selected_tags'] = ['OldTag'] + tags[1:]
    packet['tag_preflight'].update(phase='post_edit', planned_additions=tags[:1],
                                   planned_removals=['OldTag'])
    packet['tag_preflight']['current']['selected_tags'] = tags
    original = copy.deepcopy(before)
    assert approve(packet, 'publish')['status'] == 'approved'
    assert packet['tag_preflight']['baseline'] == original
    packet['tag_preflight']['planned_removals'] = []
    result = approve(packet, 'publish')
    assert result['status'] == 'blocked'
    assert 'tag_selection: tag_transition_design_mismatch' in result['reasons']


@pytest.mark.parametrize("stage", ["layout", "settings", "publish"])
@pytest.mark.parametrize("key", ["illustrations", "embeds", "review"])
def test_layout_review_missing_blocks(packet, stage, key):
    packet["layout"].pop(key)
    assert approve(packet, stage)["status"] == "blocked"


@pytest.mark.parametrize("stage", ["layout", "settings", "publish"])
def test_layout_legacy_two_choices_block(packet, stage):
    packet["layout"] = {k: packet["layout"][k] for k in ("toc", "footer_cards")}
    assert approve(packet, stage)["status"] == "blocked"


def media_plan(kind):
    item = dict(purpose="理解を補う", placement="第2節直後")
    item["source_ref" if kind == "illustrations" else "url"] = "https://example.com/media"
    return dict(decision="include", reason="説明に必要", items=[item])


@pytest.mark.parametrize("kind", ["illustrations", "embeds"])
@pytest.mark.parametrize("bad", [None, {},
    {"decision": "pending", "reason": "検討中", "items": []},
    {"decision": "omit", "reason": "", "items": []},
    {"decision": "omit", "reason": "不要", "items": [{}]},
    {"decision": "include", "reason": "必要", "items": []},
    {"decision": "include", "reason": "必要", "items": [{}]}])
def test_layout_media_requires_explicit_complete_plan(packet, kind, bad):
    packet["layout"][kind] = bad
    assert approve(packet, "layout")["status"] == "blocked"


@pytest.mark.parametrize("field", ["proposal_ref", "discussion_ref", "decision_ref"])
@pytest.mark.parametrize("bad", [None, "", "  ", "pending"])
def test_layout_review_requires_resolved_evidence(packet, field, bad):
    packet["layout"]["review"][field] = bad
    assert approve(packet, "layout")["status"] == "blocked"


@pytest.mark.parametrize("kind", ["illustrations", "embeds"])
def test_layout_media_include_and_explicit_omit_allowed(packet, kind):
    assert approve(packet, "layout")["status"] == "approved"
    packet["layout"][kind] = media_plan(kind)
    packet["receipts"] = []  # 採否変更後は旧版の承認を現在版へ流用しない。
    assert approve(packet, "layout")["status"] == "approved"


@pytest.mark.parametrize("kind", ["illustrations", "embeds"])
@pytest.mark.parametrize("field", ["purpose", "placement", "source"])
def test_layout_media_item_requires_fields(packet, kind, field):
    packet["layout"][kind] = media_plan(kind)
    if field == "source": field = "source_ref" if kind == "illustrations" else "url"
    packet["layout"][kind]["items"][0].pop(field)
    assert approve(packet, "layout")["status"] == "blocked"


@pytest.mark.parametrize("key", ["illustrations", "embeds", "review"])
@pytest.mark.parametrize("stage", ["layout", "settings", "publish"])
def test_layout_media_and_discussion_changes_invalidate(packet, key, stage):
    assert approve(packet, stage)["status"] == "approved"
    if key == "review": packet["layout"][key]["discussion_ref"] = "conversation://new-discussion"
    else: packet["layout"][key] = media_plan(key)
    assert gate.check_packet(packet, stage, "current")["status"] == "blocked"


@pytest.mark.parametrize("kind", ["illustrations", "embeds"])
def test_layout_media_edit_needs_separate_receipt(packet, kind):
    packet["layout"][kind] = media_plan(kind)
    packet["edit_plan"][kind] = packet["layout"][kind]["items"]
    assert approve(packet, "edit")["status"] == "approved"
    packet["receipts"] = [r for r in packet["receipts"] if r["stage"] != "layout"]
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


@pytest.mark.parametrize("kind", ["illustrations", "embeds"])
def test_layout_media_edit_cannot_bypass_omit(packet, kind):
    packet["edit_plan"][kind] = media_plan(kind)["items"]
    assert approve(packet, "edit")["status"] == "blocked"


@pytest.mark.parametrize("field", ["proposal_ref", "discussion_ref", "decision_ref"])
@pytest.mark.parametrize("value", ["unknown", " TODO ", "TBD", "None", " NULL ", "n/a",
    "未確認", "未定", "保留", "確認待ち", "未決定", "未承認", "検討中"])
def test_layout_review_placeholder_references_block(packet, field, value):
    packet["layout"]["review"][field] = value
    assert approve(packet, "layout")["status"] == "blocked"


@pytest.mark.parametrize("value", ["conversation://pending-discussion/123", "notes/TODO-review.md#approved",
    "conversation://未確認事項を解消した回答/456"])
def test_layout_review_legitimate_references_with_placeholder_words_allowed(packet, value):
    packet["layout"]["review"]["discussion_ref"] = value
    assert approve(packet, "layout")["status"] == "approved"


@pytest.mark.parametrize("stage", ["layout", "settings", "publish"])
@pytest.mark.parametrize("cover", [None, {}, {"decision": "omit", "reason": ""}])
def test_cover_decision_and_reason_required_even_without_image(packet, stage, cover):
    packet["layout"]["cover"] = cover
    assert packet["settings"]["cover_image"] is None
    assert approve(packet, stage)["status"] == "blocked"


@pytest.mark.parametrize("stage", ["settings", "publish"])
def test_cover_setting_must_match_layout_decision(packet, stage):
    packet["layout"]["cover"] = dict(decision="include", reason="タイトル画を採用")
    assert approve(packet, stage)["status"] == "blocked"


def test_cover_reason_change_invalidates_layout_receipt(packet):
    assert approve(packet, "layout")["status"] == "approved"
    packet["layout"]["cover"]["reason"] = "別の構成判断へ変更した"
    assert gate.check_packet(packet, "layout", "current")["status"] == "blocked"


def test_hyperlink_review_cannot_be_omitted_from_layout(packet):
    packet["layout"].pop("hyperlinks")
    assert approve(packet, "layout")["status"] == "blocked"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://user:secret@example.com", "https://example.com/\npath"])
def test_hyperlink_review_rejects_unsafe_url(packet, url):
    packet["layout"]["hyperlinks"] = dict(decision="include", reason="案内する",
        items=[dict(url=url, text="活動のページ", purpose="本人の活動を確認する", placement="末尾")])
    assert approve(packet, "layout")["status"] == "blocked"


def test_hyperlink_change_invalidates_layout_approval(packet):
    packet["layout"]["hyperlinks"] = dict(decision="include", reason="案内する",
        items=[dict(url="https://example.com/author", text="活動のページ", purpose="本人の活動を確認する", placement="末尾")])
    assert approve(packet, "layout")["status"] == "approved"
    packet["layout"]["hyperlinks"]["items"][0]["text"] = "別の表示文"
    assert gate.check_packet(packet, "layout", "current")["status"] == "blocked"


def test_hyperlink_only_edit_requires_layout_receipt_and_matching_items(packet):
    item = dict(url="https://example.com/author", text="活動のページ", purpose="活動を見る", placement="末尾")
    packet["layout"]["hyperlinks"] = dict(decision="include", reason="活動を案内", items=[item])
    packet["edit_plan"]["hyperlinks"] = [dict(item)]
    assert approve(packet, "edit")["status"] == "approved"
    packet["receipts"] = [r for r in packet["receipts"] if r["stage"] != "layout"]
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"
    packet["edit_plan"]["hyperlinks"][0]["url"] = "https://example.com/other"
    assert approve(packet, "edit")["status"] == "blocked"


@pytest.mark.parametrize("value", [[], None, "link"])
def test_link_removal_and_malformed_edit_still_require_layout_review(packet, value):
    packet["edit_plan"]["hyperlinks"] = value
    if value == []:
        assert approve(packet, "edit")["status"] == "approved"
        packet["receipts"] = [r for r in packet["receipts"] if r["stage"] != "layout"]
    assert gate.check_packet(packet, "edit", "current")["status"] == "blocked"


def test_gate_inventory_exposes_links_cards_embeds_and_tag_design(packet):
    result = gate.list_gates(packet, "current")
    layout = next(row for row in result["gates"] if row["stage"] == "layout")
    settings = next(row for row in result["gates"] if row["stage"] == "settings")
    assert {row["key"] for row in layout["review_items"]} == {
        "cover", "toc", "footer_cards", "illustrations", "embeds", "hyperlinks"}
    assert settings["tag_review"]["design"] == packet["tag_design"]
    packet["layout"].pop("hyperlinks")
    packet.pop("tag_design")
    result = gate.list_gates(packet, "current")
    layout = next(row for row in result["gates"] if row["stage"] == "layout")
    settings = next(row for row in result["gates"] if row["stage"] == "settings")
    assert next(row for row in layout["review_items"] if row["key"] == "hyperlinks")["status"] == "missing"
    assert settings["tag_review"]["status"] == "missing"


@pytest.mark.parametrize('stage', ['settings', 'publish'])
def test_adopted_tag_sources_are_required_at_workflow_entry(packet, tmp_path, stage):
    config_path = tmp_path / 'workspace-settings.json'
    config = json.loads(config_path.read_text())
    paths = {}
    for axis in ('content', 'discovery', 'branding'):
        path = tmp_path / f'marketing-{axis}.md'
        path.write_text(f'Adopted {axis} guidance.', encoding='utf-8')
        paths[axis] = str(path)
    config['tag_reference_policy'] = dict(schema='nps-tag-reference-policy/v1', required=True,
        strategy_sources={axis: [path] for axis, path in paths.items()})
    config_path.write_text(json.dumps(config))
    packet['ssot_readback'], _ = gate.read_workspace_settings(config_path, 'article')
    blocked = approve(packet, stage)
    assert 'tag_design: tag_reference_readback_missing_or_stale' in blocked['reasons']
    assert 'tag_design: tag_search_intents_missing_or_invalid' in blocked['reasons']
    packet['tag_design']['reference_readback'] = {
        path: packet['ssot_readback']['reference_hashes'][path] for path in paths.values()}
    packet['tag_design']['search_intents'] = ['論理的 人間関係', 'ASD コミュニケーション']
    for axis, path in paths.items():
        packet['tag_design']['strategy'][axis]['evidence_ref'] = path
    packet['receipts'] = []
    assert approve(packet, stage)['status'] == 'approved'
    Path(paths['discovery']).write_text('Revised search guidance.', encoding='utf-8')
    assert gate.check_packet(packet, stage, 'current')['status'] == 'blocked'


def prepare_opt_in_update(packet):
    root = Path(packet['draft']).parent
    config = root / 'workspace-settings.json'
    evidence = root / 'adoption.md'
    evidence.write_text('既存記事の依頼済み修正は公開更新まで進める')
    settings = json.loads(config.read_text())
    settings['publication_policy'] = {'existing_article_update': {
        'schema': 'nps-existing-update-policy/v1', 'enabled': True, 'account': 'nexus-ai-2045',
        'approval_ref': 'adoption.md', 'approval_sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}}
    config.write_text(json.dumps(settings))
    packet['ssot_readback'] = gate.read_workspace_settings(config, 'article')[0]
    packet['edit_plan']['target_url'] = 'https://editor.note.com/notes/n123abc/edit/'
    packet['update_observation'] = {
        'operation': 'update_existing', 'published_before': True, 'account': 'nexus-ai-2045', 'note_id': 'n123abc',
        'public_url': 'https://note.com/nexus-ai-2045/n/n123abc', 'action': '更新する',
        'new_publication': False, 'schedule_change': False, 'external_share': False,
        **dict.fromkeys(('approved_content_sha256', 'editor_content_sha256', 'saved_content_sha256'),
                        hashlib.sha256(Path(packet['draft']).read_bytes()).hexdigest()),
        **dict.fromkeys(('baseline_settings_sha256', 'current_settings_sha256'),
                        gate.canonical_sha256(packet['settings'])),
        'edit_request_ref': 'current-user-request', 'checks': dict.fromkeys((
            'requested_change_only', 'body_and_links_verified', 'layout_verified', 'saved_and_reloaded',
            'public_identity_verified', 'prepublish_qa_passed'), True)}


def test_opt_in_update_waives_only_final_publish_receipt(packet):
    prepare_opt_in_update(packet)
    result = approve(packet, 'publish')
    packet['receipts'].append(dict(article_id=packet['article_id'], conversation_id='current',
        stage='update_request', subject_sha256=result['subject_hashes']['publish'], actor='user',
        status='approved', evidence_ref='current-user-request', observed_at='2026-10-05T10:00:00+09:00',
        operation='update_existing', note_id='n123abc'))
    packet['receipts'] = [r for r in packet['receipts'] if r['stage'] != 'publish']
    result = gate.check_packet(packet, 'publish', 'current')
    assert result['status'] == 'approved' and result['automation_allowed'] is True
    assert result['manual_publish_required'] is False
    # 調査の確認は継続許可で代替しない。
    research = next(r for r in packet['receipts'] if r['stage'] == 'research')
    packet['receipts'].remove(research)
    result = gate.check_packet(packet, 'publish', 'current')
    assert result['status'] == 'blocked' and result['automation_allowed'] is False
    packet['receipts'].append(research)
    packet['update_observation']['saved_content_sha256'] = 'c'*64
    assert gate.check_packet(packet, 'publish', 'current')['automation_allowed'] is False


@pytest.mark.parametrize('change,reason', [
    ('draft', 'update_current_content_mismatch'),
    ('settings', 'update_current_settings_mismatch'),
    ('equal_forged_hashes', 'update_current_content_mismatch'),
    ('scheduled', 'update_operation_outside_scope'),
    ('sns_share', 'update_operation_outside_scope'),
])
def test_opt_in_update_binds_current_packet_and_operation_scope(packet, change, reason):
    prepare_opt_in_update(packet)
    prepared = approve(packet, 'publish')
    packet['receipts'].append(dict(article_id=packet['article_id'], conversation_id='current',
        stage='update_request', subject_sha256=prepared['subject_hashes']['publish'], actor='user',
        status='approved', evidence_ref='current-user-request', observed_at='2026-10-05T10:00:00+09:00',
        operation='update_existing', note_id='n123abc'))
    assert gate.check_packet(packet, 'publish', 'current')['status'] == 'approved'
    if change == 'draft':
        Path(packet['draft']).write_text('更新観測後に変更した本文', encoding='utf-8')
    elif change == 'settings':
        packet['settings']['magazine'] = '別のマガジン'
    elif change == 'equal_forged_hashes':
        for key in ('approved_content_sha256', 'editor_content_sha256', 'saved_content_sha256'):
            packet['update_observation'][key] = 'c'*64
    else:
        if change == 'scheduled':
            packet['settings'].update(publish_mode='scheduled', schedule_at='2026-10-23T10:00:00+09:00')
        else:
            packet['settings']['sns_share'] = True
        # 設定hashが実値と一致しても、観測のfalse宣言で予約/共有を許可できない。
        for key in ('baseline_settings_sha256', 'current_settings_sha256'):
            packet['update_observation'][key] = gate.canonical_sha256(packet['settings'])
    result = gate.check_packet(packet, 'publish', 'current')
    assert result['status'] == 'blocked'
    assert result['automation_allowed'] is False
    assert result['update_authorization']['reason'] == reason


@pytest.mark.parametrize('change', ['missing', 'other-conversation', 'other-request', 'other-note'])
def test_update_policy_requires_current_bound_user_request(packet, change):
    # 既存の成功経路で作ったpacketから、現在依頼の束縛だけを壊す。
    test_opt_in_update_waives_only_final_publish_receipt(packet)
    packet['update_observation']['saved_content_sha256'] = packet['update_observation']['approved_content_sha256']
    request = next(r for r in packet['receipts'] if r['stage'] == 'update_request')
    if change == 'missing': packet['receipts'].remove(request)
    elif change == 'other-conversation': request['conversation_id'] = 'old'
    elif change == 'other-request': request['evidence_ref'] = 'old-request'
    else: request['note_id'] = 'nother'
    result = gate.check_packet(packet, 'publish', 'current')
    assert result['status'] == 'blocked' and result['automation_allowed'] is False

def test_global_fidelity_required_cannot_be_disabled_in_article_profile(packet):
    root = Path(packet['draft']).parent
    config = root / 'workspace-settings.json'
    value = json.loads(config.read_text())
    source = Path(packet['source_snapshot'])
    policy = dict(schema='note-conversation-fidelity-policy/v1', required=True,
                  source=str(source), sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    value['conversation_fidelity_policy'] = policy
    value['style']['article_profiles']['article'] = dict(references=['profile.md'],
        conversation_fidelity_policy=dict(schema=policy['schema'],required=False))
    config.write_text(json.dumps(value))
    expected,_ = gate.read_workspace_settings(config,'article')
    assert expected['conversation_fidelity_policy']['required'] is True


def test_edit_workflow_runs_required_fidelity_on_proposal(packet):
    root = Path(packet['draft']).parent
    config = root / 'workspace-settings.json'
    value = json.loads(config.read_text())
    source = Path(packet['source_snapshot'])
    value['conversation_fidelity_policy'] = dict(schema='note-conversation-fidelity-policy/v1', required=True,
        source=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    config.write_text(json.dumps(value))
    packet['ssot_readback'],_ = gate.read_workspace_settings(config,'article')
    result = gate.check_packet(packet,'edit','current')
    assert result['status'] == 'blocked'
    assert 'conversation_fidelity' in result
    assert result['conversation_fidelity']['errors']


def test_progress_proof_is_observed_without_changing_approval_subject(packet, monkeypatch):
    import types
    original_loader = gate._load_sibling_module
    config = Path(packet['draft']).parent / 'workspace-settings.json'
    settings = json.loads(config.read_text())
    settings['conversation_fidelity_policy'] = dict(schema='note-conversation-fidelity-policy/v1',
        required=True, source=packet['source_snapshot'],
        sha256=hashlib.sha256(Path(packet['source_snapshot']).read_bytes()).hexdigest(),
        allow_reviewed_progress_tail=True)
    config.write_text(json.dumps(settings))
    packet['ssot_readback'], _ = gate.read_workspace_settings(config, 'article')
    material = dict(draft=hashlib.sha256(Path(packet['proposed_draft']).read_bytes()).hexdigest(),
                    source='base-source', mapping='base-mapping', review='base-review')
    proof = dict(tail_review='tail-review-one', latest_source='capture-one', latest_prefix='prefix-one')
    def fidelity(*args):
        return dict(status='mechanical_ok', errors=[], approval_hashes=dict(material), hashes={**material, **proof})
    monkeypatch.setattr(gate, '_load_sibling_module', lambda name:
        types.SimpleNamespace(check_conversation_fidelity=fidelity) if name == 'provenance_label_check'
        else original_loader(name))
    before = approve(packet, 'edit')
    assert before['status'] == 'approved', before
    proof.update(tail_review='tail-review-two', latest_source='capture-two', latest_prefix='prefix-two')
    after = gate.check_packet(packet, 'edit', 'current')
    assert after['status'] == 'approved', after
    assert before['subject_hashes'] == after['subject_hashes']
    assert after['conversation_fidelity']['hashes']['tail_review'] == 'tail-review-two'
    material['source'] = 'changed-material'
    changed = gate.check_packet(packet, 'edit', 'current')
    assert changed['status'] == 'blocked'
    assert changed['subject_hashes'] != before['subject_hashes']
