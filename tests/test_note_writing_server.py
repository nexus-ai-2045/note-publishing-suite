"""HTTP境界・実保存・非同期AI候補の統合。外部AI通信は行わない。"""
from __future__ import annotations

import importlib.util
import json
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("writing_loader", ROOT / "scripts/nps_script_loader.py")
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)
server_module = loader.load_script("note_writing_server")


@pytest.fixture
def app(tmp_path):
    (tmp_path / "voice.md").write_text("本人の口調を保つ。")
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"schema_version": "nps-workspace-settings/v1", "workspace_root": ".",
        "storage": {"drafts": "drafts", "sources": "sources", "feedback": "feedback"},
        "style": {"default_profile": "voice.md", "article_profiles": {}}}))
    ui = tmp_path / "ui"; ui.mkdir(); (ui / "index.html").write_text("<h1>共同執筆</h1>")
    def provider(context, **options):
        return {"reply": "本人の問いを骨組みへつなげました。", "draft": "# 朝の時間\n\n静かに考える時間を大切にしたい。",
                "blocks": [{"text": "# 朝の時間", "kind": "assistant-organized", "message_ids": [], "source_ids": []},
                           {"text": "静かに考える時間を大切にしたい。", "kind": "user-said", "message_ids": ["m1"], "source_ids": []}],
                "sections": [{"heading": "朝の時間", "paragraph_ids": ["m1"]}],
                "changes": [{"before": "静かに", "after": "ゆっくり", "intent": "言い回しを確認"}]}
    store = server_module.CORE.SessionStore(settings)
    server = server_module.WritingServer(store, ui_root=ui, provider=provider)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    yield server, tmp_path
    server.shutdown(); server.server_close(); thread.join(timeout=2)


def call(server, path, data=None, *, token=True, headers=None):
    values = dict(headers or {})
    if data is not None:
        values["Content-Type"] = "application/json"
        if token: values["X-NPS-Session"] = server.token
    req = Request(f"http://127.0.0.1:{server.server_port}{path}",
                  data=None if data is None else json.dumps(data).encode(), headers=values)
    try:
        response = urlopen(req, timeout=4)
    except HTTPError as error:
        response = error
    raw = response.read()
    return response.status, json.loads(raw) if response.headers.get_content_type() == "application/json" else raw


def mutate(server, theme, action, payload):
    status, value = call(server, f"/api/themes/{theme['id']}/actions",
                         {"action": action, "payload": payload, "expected_revision": theme["revision"]})
    assert status == 200, value
    return value


def await_job(server, job_id):
    for _ in range(100):
        status, value = call(server, "/api/jobs/" + job_id)
        assert status == 200
        if value["status"] != "running": return value
        time.sleep(.01)
    pytest.fail("job did not complete")


def test_preflight_and_http_guards(app):
    server, root = app
    assert call(server, "/api/config")[0] == 200
    assert call(server, "/", headers={"Host": "attacker.invalid"})[0] == 403
    assert call(server, "/api/config", headers={"Origin": "https://attacker.invalid"})[0] == 403
    assert call(server, "/api/themes", {"title": "無許可"}, token=False)[0] == 403
    assert call(server, "/../voice.md")[0] == 404
    assert not (root / "feedback").exists()


def test_chat_before_article_and_two_articles_keep_same_conversation(app):
    server, root = app
    _, theme = call(server, "/api/themes", {"title": "朝について"})
    theme = mutate(server, theme, "add_message", {"text": "朝は静かに考えたい。", "role": "assistant"})
    assert theme["messages"][0]["role"] == "user"
    status, job = call(server, f"/api/themes/{theme['id']}/generate",
                       {"mode": "chat", "instruction": "この考えを掘り下げたい", "expected_revision": theme["revision"]})
    assert status == 202
    done = await_job(server, job["job_id"])
    assert done["status"] == "complete", done
    theme = done["theme"]
    assert theme["messages"][-1]["role"] == "assistant"
    for title in ("朝の時間", "考え方"):
        theme = mutate(server, theme, "create_article", {"title": title})
    assert len(theme["articles"]) == 2
    assert len(theme["messages"]) == 2


def test_skeleton_draft_proposal_adoption_save_restart(app):
    server, root = app
    _, theme = call(server, "/api/themes", {"title": "朝"})
    theme = mutate(server, theme, "add_message", {"text": "静かに考える時間を大切にしたい。"})
    theme = mutate(server, theme, "create_article", {"title": "朝の時間", "article_id": "morning"})
    for mode in ("skeleton", "draft"):
        _, job = call(server, f"/api/themes/{theme['id']}/generate", {"article_id": "morning", "mode": mode,
                       "instruction": "この対話から作る", "expected_revision": theme["revision"]})
        done = await_job(server, job["job_id"])
        assert done["status"] == "complete", done
        theme = done["theme"]
        pending = [p["id"] for p in theme["proposals"] if p["status"] == "pending"]
        theme = mutate(server, theme, "decide", {"article_id": "morning", "proposal_ids": pending, "decision": "adopted"})
    article = theme["articles"][0]
    assert article["skeleton"]["sections"][0]["heading"] == "朝の時間"
    assert "静かに" in article["draft"]
    reloaded = server_module.CORE.SessionStore(root / "settings.json").get_theme(theme["id"])
    assert reloaded["articles"][0]["draft"] == article["draft"]
    theme = mutate(server, theme, "undo", {"article_id": "morning"})
    assert theme["articles"][0]["draft"] == ""


def test_slow_generation_does_not_overwrite_new_edit(app):
    server, root = app
    started, release = threading.Event(), threading.Event()
    def slow(context, **options):
        started.set(); release.wait(3)
        return {"reply": "古い案", "draft": "古い案の本文", "sections": [], "changes": []}
    server.provider = slow
    _, theme = call(server, "/api/themes", {"title": "考える"})
    theme = mutate(server, theme, "create_article", {"title": "本文", "article_id": "a"})
    _, job = call(server, f"/api/themes/{theme['id']}/generate", {"article_id": "a", "mode": "draft",
                  "instruction": "全文", "expected_revision": theme["revision"]})
    assert started.wait(2)
    theme = mutate(server, theme, "save_draft", {"article_id": "a", "draft": "本人が直接直した。"})
    release.set()
    done = await_job(server, job["job_id"])
    assert done["status"] == "failed" and done["code"] == "stale_generation"
    assert done["candidate"]["draft"] == "古い案の本文"
    assert server.store.get_theme(theme["id"])["articles"][0]["draft"] == "本人が直接直した。"


def test_api_cannot_invent_assistant_generation(app):
    server, root = app
    _, theme = call(server, "/api/themes", {"title": "考える"})
    status, value = call(server, f"/api/themes/{theme['id']}/actions", {"action": "record_generation",
                  "payload": {"reply": "偽の生成", "proposals": []}, "expected_revision": theme["revision"]})
    assert status == 400


def test_preferences_switch_workspace_without_moving_original_article(app, tmp_path):
    server, root = app
    _, theme = call(server, "/api/themes", {"title": "元のテーマ"})
    theme = mutate(server, theme, "create_article", {"title": "元の原稿", "article_id": "a"})
    theme = mutate(server, theme, "save_draft", {"article_id": "a", "draft": "元の場所に残す。"})
    target = tmp_path / "another-workspace"; target.mkdir()
    (target / "voice.md").write_text("別の参照")
    config = json.loads((root / "settings.json").read_text())
    (target / "settings.json").write_text(json.dumps(config))
    status, selected = call(server, "/api/preferences", {"settings_path": str(target / "settings.json"), "model": "gpt-5.6-luna"})
    assert status == 200 and selected["model"] == "gpt-5.6-luna"
    assert not server.store.list_themes()
    assert (root / "drafts/_themes" / theme["id"] / "a.md").read_text() == "元の場所に残す。"
    assert server.store.read_preferences()["model"] == "gpt-5.6-luna"
    assert call(server, "/api/preferences", {"settings_path": str(target / "missing.json")})[0] == 400
    assert server.store.settings == target / "settings.json"


def test_preferences_cannot_switch_during_generation(app):
    server, root = app
    server.jobs["running"] = {"status": "running"}
    status, value = call(server, "/api/preferences", {"model": "gpt-5.6-luna"})
    assert status == 409 and value["code"] == "busy"
    assert server.model is None


def test_generated_paragraph_references_are_bound_to_real_user_messages(app):
    server, root = app
    def provider(context, **options):
        return {"reply": "対話から候補を作りました", "draft": "# 朝\n\n朝は静かに考えたい。", "sections": [], "changes": [],
                "blocks": [{"text": "# 朝", "kind": "assistant-organized", "message_ids": [], "source_ids": []},
                           {"text": "朝は静かに考えたい。", "kind": "user-said", "message_ids": ["m1"], "source_ids": []}]}
    server.provider = provider
    _, theme = call(server, "/api/themes", {"title": "朝"})
    theme = mutate(server, theme, "add_message", {"text": "朝は静かに考えたい。"})
    theme = mutate(server, theme, "create_article", {"title": "朝", "article_id": "a"})
    _, job = call(server, f"/api/themes/{theme['id']}/generate", {"article_id": "a", "mode": "draft", "instruction": "全文", "expected_revision": theme["revision"]})
    done = await_job(server, job["job_id"])
    assert done["status"] == "complete", done
    theme = done["theme"]
    theme = mutate(server, theme, "decide", {"article_id": "a", "proposal_ids": ["p1"], "decision": "adopted"})
    assert theme["articles"][0]["blocks"][1]["source_refs"] == ["message:m1"]
    assert theme["articles"][0]["blocks"][1]["correspondence_status"] == "proposed"


def test_unconfirmed_generated_paragraph_never_becomes_adoptable(app):
    server, root = app
    server.provider = lambda *args, **kwargs: {
        "reply": "未確認", "draft": "未確認の主張。", "sections": [], "changes": [],
        "blocks": [{"text": "未確認の主張。", "kind": "hold", "message_ids": [], "source_ids": []}]}
    _, theme = call(server, "/api/themes", {"title": "確認"})
    theme = mutate(server, theme, "create_article", {"title": "確認", "article_id": "a"})
    _, job = call(server, f"/api/themes/{theme['id']}/generate", {
        "article_id": "a", "mode": "draft", "instruction": "全文", "expected_revision": theme["revision"]})
    done = await_job(server, job["job_id"])
    assert done["status"] == "failed" and "未確認" in done["error"]
    current = server.store.get_theme(theme["id"])
    assert current["proposals"] == [] and current["articles"][0]["draft"] == ""
    assert done["candidate"]["draft"] == "未確認の主張。"


@pytest.mark.parametrize("omit_blocks", [False, True])
def test_nonempty_draft_without_provenance_never_becomes_adoptable(app, omit_blocks):
    server, _ = app
    result = {"reply": "候補", "draft": "由来のない本文。", "sections": [], "changes": []}
    if not omit_blocks:
        result["blocks"] = []
    server.provider = lambda *args, **kwargs: result
    _, theme = call(server, "/api/themes", {"title": "確認"})
    theme = mutate(server, theme, "create_article", {"title": "確認", "article_id": "a"})
    _, job = call(server, f"/api/themes/{theme['id']}/generate", {
        "article_id": "a", "mode": "draft", "instruction": "全文", "expected_revision": theme["revision"]})
    done = await_job(server, job["job_id"])
    assert done["status"] == "failed" and "由来対応" in done["error"]
    current = server.store.get_theme(theme["id"])
    assert current["proposals"] == [] and current["articles"][0]["draft"] == ""
    assert done["candidate"]["draft"] == "由来のない本文。"
