from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "note_collaborative_session.py"
spec = importlib.util.spec_from_file_location("note_collaborative_session", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


@pytest.fixture
def store(tmp_path):
    (tmp_path / "voice.md").write_text("声", encoding="utf-8")
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"schema_version": "nps-workspace-settings/v1", "workspace_root": ".",
        "storage": {"drafts": "drafts", "sources": "sources", "feedback": "feedback"},
        "style": {"default_profile": "voice.md", "article_profiles": {}}}), encoding="utf-8")
    return module.SessionStore(settings), tmp_path


def test_theme_articles_draft_and_restart(store):
    db, root = store
    assert db.preflight()["ok"]
    capabilities = db.preflight()["capabilities"]
    assert not capabilities["atomic_writes"] and not capabilities["cas"]
    assert capabilities["metadata_atomic_writes"] and capabilities["cooperative_revision_cas"]
    assert capabilities["displaced_draft_inode_preserved"]
    theme = db.create_theme("二つの記事", "theme")
    theme = db.mutate("theme", "create_article", {"title": "一話", "article_id": "one"}, 0)
    db.mutate("theme", "create_article", {"title": "二話", "article_id": "two"}, 1)
    db.mutate("theme", "save_draft", {"article_id": "one", "draft": "本文"}, 2)
    assert (root / "drafts/_themes/theme/one.md").read_text(encoding="utf-8") == "本文"
    assert module.SessionStore(root / "settings.json").get_theme("theme")["articles"][0]["draft"] == "本文"


def test_proposal_decision_stale_and_undo(store):
    db, _ = store
    db.create_theme("t", "t")
    db.mutate("t", "create_article", {"article_id": "a", "title": "A"}, 0)
    db.mutate("t", "save_draft", {"article_id": "a", "draft": "old"}, 1)
    value = db.mutate("t", "propose", {"article_id": "a", "before": "old", "after": "new", "intent": "明確化"}, 2)
    db.mutate("t", "decide", {"article_id": "a", "proposal_ids": ["p1"], "decision": "adopted"}, value["revision"])
    assert db.get_theme("t")["articles"][0]["draft"] == "new"
    db.mutate("t", "undo", {"article_id": "a"}, 4)
    assert db.get_theme("t")["articles"][0]["draft"] == "old"
    with pytest.raises(module.SessionError) as exc:
        db.mutate("t", "save_draft", {"article_id": "a", "draft": "x"}, 0)
    assert exc.value.code == "stale"


def test_dry_run_and_traversal_are_side_effect_free(store):
    db, root = store
    db.create_theme("t", "t")
    result = db.mutate("t", "create_article", {"article_id": "a", "title": "A"}, 0, dry_run=True)
    assert result["articles"] and not (root / "drafts").exists()
    with pytest.raises(module.SessionError):
        db.mutate("t", "add_source", {"path": "../outside.txt"}, 0)


def article_ready(store):
    db, root = store
    db.create_theme("考える", "t")
    t = db.mutate("t", "create_article", {"article_id": "a", "title": "A"}, 0)
    return db, root, db.mutate("t", "save_draft", {"article_id": "a", "draft": "前半。\n\n後半。"}, t["revision"])


def test_existing_feedback_is_written_and_readable(store):
    db, root, theme = article_ready(store)
    path = root / "feedback/nps-1-t-a/feedback.json"
    record = json.loads(path.read_text())
    assert record["article_id"] == "nps-1-t-a"
    assert record["entries"][0]["origin"] == "author"
    assert list((root / "feedback/nps-1-t-a/snapshots").glob("*.txt"))
    db.mutate("t", "propose", {"article_id": "a", "before": "前半。", "after": "新しい前半。", "intent": "更新"}, theme["revision"])
    assert json.loads(path.read_text())["entries"][0]["decision"] == "pending"


def test_disjoint_batch_is_one_undo_and_no_second_application(store):
    db, root, t = article_ready(store)
    for old, new in [("前半。", "最初。"), ("後半。", "最後。")]:
        t = db.mutate("t", "propose", {"article_id": "a", "before": old, "after": new, "intent": "更新"}, t["revision"])
    t = db.mutate("t", "decide", {"article_id": "a", "proposal_ids": ["p1", "p2"], "decision": "adopted"}, t["revision"])
    assert t["articles"][0]["draft"] == "最初。\n\n最後。"
    with pytest.raises(module.SessionError, match="採用済み"):
        db.mutate("t", "decide", {"article_id": "a", "proposal_ids": ["p1"], "decision": "adopted"}, t["revision"])
    t = db.mutate("t", "undo", {"article_id": "a"}, t["revision"])
    assert t["articles"][0]["draft"] == "前半。\n\n後半。"
    assert all(p["status"] == "pending" for p in t["proposals"])
    t = db.mutate("t", "redo", {"article_id": "a"}, t["revision"])
    assert t["articles"][0]["draft"] == "最初。\n\n最後。"


def test_overlap_is_rejected_without_partial_changes(store):
    db, root, t = article_ready(store)
    for before in ["前半。", "前半。\n\n後半。"]:
        t = db.mutate("t", "propose", {"article_id": "a", "before": before, "after": "変更。", "intent": "更新"}, t["revision"])
    with pytest.raises(module.SessionError) as error:
        db.mutate("t", "decide", {"article_id": "a", "proposal_ids": ["p1", "p2"], "decision": "adopted"}, t["revision"])
    assert error.value.code == "overlap"
    assert db.get_theme("t")["articles"][0]["draft"] == "前半。\n\n後半。"


@pytest.mark.parametrize("change", ["draft", "message", "skeleton"])
def test_old_proposal_cannot_overwrite_new_thinking(store, change):
    db, root, t = article_ready(store)
    t = db.mutate("t", "propose", {"article_id": "a", "before": "前半。", "after": "変更。", "intent": "更新"}, t["revision"])
    action, payload = {"draft": ("save_draft", {"article_id": "a", "draft": "本人が直した本文。"}),
                       "message": ("add_message", {"role": "user", "text": "考えが変わった"}),
                       "skeleton": ("set_skeleton", {"article_id": "a", "skeleton": {"sections": []}})}[change]
    t = db.mutate("t", action, payload, t["revision"])
    with pytest.raises(module.SessionError) as error:
        db.mutate("t", "decide", {"article_id": "a", "proposal_ids": ["p1"], "decision": "adopted"}, t["revision"])
    assert error.value.code == "stale_proposal"


def test_external_edit_requires_explicit_reload_and_keeps_local_text(store):
    db, root, t = article_ready(store)
    path = root / "drafts/_themes/t/a.md"
    path.write_text("外部で本人が直した。")
    assert db.get_theme("t")["conflicts"][0]["kind"] == "external_edit"
    with pytest.raises(module.SessionError) as error:
        db.mutate("t", "save_draft", {"article_id": "a", "draft": "古い内容"}, t["revision"])
    assert error.value.code == "external_edit"
    t = db.mutate("t", "reload_draft", {"article_id": "a"}, t["revision"])
    assert t["articles"][0]["draft"] == "外部で本人が直した。"
    assert not db.get_theme("t")["conflicts"]


def test_source_snapshot_is_preserved_and_tamper_detected(store):
    db, root, t = article_ready(store)
    source = root / "material.md"; source.write_text("本人の原文。")
    t = db.mutate("t", "add_source", {"path": "material.md"}, t["revision"])
    source.write_text("原資料の後の版。")
    assert db.get_theme("t")["sources"][0]["text"] == "本人の原文。"
    snapshot = next((root / "sources/_themes/t").glob("*.snapshot"))
    snapshot.write_text("改変")
    with pytest.raises(module.SessionError) as error:
        db.get_theme("t")
    assert error.value.code == "source_corrupt"


def test_theme_symlink_is_rejected(store, tmp_path):
    db, root = store
    db.preflight()
    (root / "feedback/_themes").mkdir(parents=True)
    elsewhere = root / "elsewhere"; elsewhere.mkdir()
    (root / "feedback/_themes/escape").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(module.SessionError) as error:
        db.create_theme("escape", "escape")
    assert error.value.code == "symlink_path"


def test_preflight_and_create_dry_run_never_make_storage(store):
    db, root = store
    db.preflight(); db.create_theme("試す", dry_run=True)
    assert not any((root / name).exists() for name in ("sources", "drafts", "feedback"))


def test_save_failure_rolls_back_and_retains_old_feedback(store, monkeypatch):
    db, root, t = article_ready(store)
    old_feedback = (root / "feedback/nps-1-t-a/feedback.json").read_bytes()
    original = module._atomic
    fired = False
    def fail_once(path, data):
        nonlocal fired
        if path.name == "session.json" and not fired:
            fired = True
            raise OSError("simulated disk failure")
        return original(path, data)
    monkeypatch.setattr(module, "_atomic", fail_once)
    with pytest.raises(OSError):
        db.mutate("t", "save_draft", {"article_id": "a", "draft": "失敗する更新"}, t["revision"])
    assert db.get_theme("t")["articles"][0]["draft"] == "前半。\n\n後半。"
    assert (root / "feedback/nps-1-t-a/feedback.json").read_bytes() == old_feedback


def test_skeleton_proposal_does_not_overwrite_draft(store):
    db, root, t = article_ready(store)
    t = db.mutate("t", "propose", {"article_id": "a", "target": "skeleton", "before": json.dumps({"sections": []}),
                     "after": json.dumps({"sections": [{"id": "s1", "heading": "問い", "paragraph_ids": []}]}), "intent": "構成案"}, t["revision"])
    t = db.mutate("t", "decide", {"article_id": "a", "proposal_ids": ["p1"], "decision": "adopted"}, t["revision"])
    assert t["articles"][0]["skeleton"]["sections"][0]["heading"] == "問い"
    assert t["articles"][0]["draft"] == "前半。\n\n後半。"


def test_generation_records_every_pending_proposal_in_existing_feedback(store):
    db, root, t = article_ready(store)
    t = db.mutate("t", "record_generation", {"reply": "2箇所の候補です", "proposals": [
        {"article_id": "a", "before": "前半。", "after": "最初。", "intent": "一つ目"},
        {"article_id": "a", "before": "後半。", "after": "最後。", "intent": "二つ目"}]}, t["revision"])
    record, verified = module._FEEDBACK.read_feedback_record(db._dirs, "nps-1-t-a")
    assert [e["reason"] for e in record["entries"]] == ["一つ目", "二つ目"]
    assert len(t["proposals"]) == 2


def test_clearing_a_working_draft_updates_feedback_instead_of_leaving_old_snapshot(store):
    db, root, t = article_ready(store)
    t = db.mutate("t", "save_draft", {"article_id": "a", "draft": ""}, t["revision"])
    record, verified = module._FEEDBACK.read_feedback_record(db._dirs, "nps-1-t-a")
    assert record["entries"][0]["after"] == ""
    assert record["snapshot_hashes"]["draft"] == module._sha(b"")
    assert (root / "drafts/_themes/t/a.md").read_bytes() == b""


def test_feedback_namespace_separates_ambiguous_theme_article_pairs(store):
    db, root = store
    for theme_id, article_id in [("t--x", "a"), ("t", "x--a")]:
        t = db.create_theme("別々のテーマ", theme_id)
        t = db.mutate(theme_id, "create_article", {"article_id": article_id}, t["revision"])
        db.mutate(theme_id, "save_draft", {"article_id": article_id, "draft": theme_id}, t["revision"])
    first = db.feedback_article_id("t--x", "a")
    second = db.feedback_article_id("t", "x--a")
    assert first != second
    one, _ = module._FEEDBACK.read_feedback_record(db._dirs, first)
    two, _ = module._FEEDBACK.read_feedback_record(db._dirs, second)
    assert one["conversation_id"] == "nps-theme:t--x"
    assert two["conversation_id"] == "nps-theme:t"


def recovery_journal(root, rows):
    journal = root / "feedback/_themes/t/transaction.json"
    journal.write_text(json.dumps({"backups": rows}))
    return journal


def test_corrupt_late_recovery_item_does_not_partly_rollback(store):
    import base64
    db, root, theme = article_ready(store)
    draft = root / "drafts/_themes/t/a.md"
    journal = recovery_journal(root, [{"path": "drafts/_themes/t/a.md", "value": base64.b64encode(b"old").decode()},
                                      {"path": "sources/_themes/t/extra.snapshot", "value": "!broken!"}])
    before = draft.read_bytes()
    with pytest.raises(ValueError): db.mutate("t", "recover", {}, theme["revision"])
    assert draft.read_bytes() == before and journal.exists()


@pytest.mark.parametrize("target", ["drafts/_themes/other/a.md", "feedback/_themes/other/session.json", "feedback/nps-5-other-a/feedback.json"])
def test_recovery_never_modifies_another_theme(store, target):
    import base64
    db, root, theme = article_ready(store)
    journal = recovery_journal(root, [{"path": target, "value": base64.b64encode(b"old").decode()}])
    with pytest.raises(module.SessionError) as error:
        db.mutate("t", "recover", {}, theme["revision"])
    assert error.value.code == "invalid_recovery" and journal.exists()
    assert not (root / target).exists()


def test_recovery_write_failure_keeps_pre_recovery_files_and_journal(store, monkeypatch):
    import base64
    db, root, theme = article_ready(store)
    draft = root / "drafts/_themes/t/a.md"
    other = root / "sources/_themes/t/recover.snapshot"; other.write_bytes(b"current")
    journal = recovery_journal(root, [{"path": "drafts/_themes/t/a.md", "value": base64.b64encode(b"old").decode()},
                                      {"path": "sources/_themes/t/recover.snapshot", "value": base64.b64encode(b"previous").decode()}])
    before = draft.read_bytes(); original = module._atomic; fired = False
    def fail_once(path, data):
        nonlocal fired
        if path == other and not fired:
            fired = True; raise OSError("simulated recovery failure")
        original(path, data)
    monkeypatch.setattr(module, "_atomic", fail_once)
    with pytest.raises(OSError): db.mutate("t", "recover", {}, theme["revision"])
    assert draft.read_bytes() == before and other.read_bytes() == b"current" and journal.exists()


def test_recovery_dry_run_is_read_only_then_recovery_succeeds(store):
    import base64
    db, root, theme = article_ready(store)
    journal = recovery_journal(root, [{"path": "drafts/_themes/t/a.md", "value": base64.b64encode(b"old").decode()}])
    before = (root / "drafts/_themes/t/a.md").read_bytes()
    plan = db.mutate("t", "recover", {}, theme["revision"], dry_run=True)
    assert plan["recovery_targets"] == ["drafts/_themes/t/a.md"]
    assert (root / "drafts/_themes/t/a.md").read_bytes() == before and journal.exists()
    db.mutate("t", "recover", {}, theme["revision"])
    assert (root / "drafts/_themes/t/a.md").read_bytes() == b"old" and not journal.exists()


def test_interrupted_transaction_recovers_draft_feedback_and_session_together(store, monkeypatch):
    db, root, theme = article_ready(store)
    feedback = root / "feedback/nps-1-t-a/feedback.json"
    original_feedback = feedback.read_bytes()
    original = module._atomic
    def interrupted(path, data):
        if path.name == "session.json":
            raise KeyboardInterrupt("simulated process interruption")
        original(path, data)
    monkeypatch.setattr(module, "_atomic", interrupted)
    with pytest.raises(KeyboardInterrupt):
        db.mutate("t", "save_draft", {"article_id": "a", "draft": "中断した更新。"}, theme["revision"])
    monkeypatch.setattr(module, "_atomic", original)
    with pytest.raises(module.SessionError) as error:
        db.get_theme("t")
    assert error.value.code == "recovery_required"
    restored = module.SessionStore(root / "settings.json").mutate("t", "recover", {}, theme["revision"])
    assert restored["revision"] == theme["revision"]
    assert restored["articles"][0]["draft"] == "前半。\n\n後半。"
    assert feedback.read_bytes() == original_feedback


def test_open_existing_draft_and_skeleton_keeps_original_paths_and_bytes(store):
    db, root = store
    (root / "drafts").mkdir()
    original = root / "drafts/current.md"
    original.write_bytes(b"---\ntitle: Current\n---\n\n<!-- paragraph-id: p1 -->\nOriginal.\n")
    skeleton = root / "skeleton.json"
    skeleton.write_text(json.dumps({"episodes": [{"n": 7, "sections": [{"heading": "問い", "paragraphs": [{"id": "p1", "text": "Original."}]}]}]}))
    before, skeleton_before = original.read_bytes(), skeleton.read_bytes()
    theme = db.create_theme("既存稿", "existing")
    theme = db.mutate("existing", "open_article", {"draft_path": "drafts/current.md", "skeleton_path": "skeleton.json", "episode": 7}, theme["revision"])
    assert original.read_bytes() == before and skeleton.read_bytes() == skeleton_before
    assert theme["articles"][0]["skeleton"]["sections"][0]["paragraph_ids"] == ["p1"]
    assert theme["articles"][0]["blocks"][0]["source_refs"] == ["paragraph:p1"]
    assert not (root / "drafts/_themes/existing").exists()
    theme = db.mutate("existing", "save_draft", {"article_id": "article-1", "draft": before.decode().replace("Original.", "Edited.")}, theme["revision"])
    assert b"Edited." in original.read_bytes() and skeleton.read_bytes() == skeleton_before
    db.create_theme("別テーマ", "other")
    with pytest.raises(module.SessionError) as error:
        db.mutate("other", "open_article", {"draft_path": "drafts/current.md"}, 0)
    assert error.value.code == "already_open"


def test_existing_draft_outside_adopted_drafts_is_rejected_without_changes(store):
    db, root = store
    source = root / "outside.md"; source.write_text("読み物")
    db.create_theme("t", "t")
    with pytest.raises(module.SessionError) as error:
        db.mutate("t", "open_article", {"draft_path": "outside.md"}, 0)
    assert error.value.code == "invalid_draft" and source.read_text() == "読み物"


def test_future_learning_is_opt_in_survives_saves_and_can_be_revoked(store):
    db, root, theme = article_ready(store)
    theme = db.mutate("t", "propose", {"article_id": "a", "before": "前半。", "after": "まず考える。", "intent": "語尾の参考"}, theme["revision"])
    assert not db.generation_references("another")["learning_examples"]
    theme = db.mutate("t", "decide", {"article_id": "a", "proposal_ids": ["p1"], "decision": "adopted", "scope": "future"}, theme["revision"])
    assert db.generation_references("another")["learning_examples"][0]["after"] == "まず考える。"
    theme = db.mutate("t", "save_draft", {"article_id": "a", "draft": "まず考える。\n\n次に書く。"}, theme["revision"])
    assert len(db.generation_references("another")["learning_examples"]) == 1
    theme = db.mutate("t", "revoke_learning", {"article_id": "a", "proposal_id": "p1"}, theme["revision"])
    assert not db.generation_references("another")["learning_examples"]
    assert theme["articles"][0]["draft"] == "まず考える。\n\n次に書く。"


def test_undo_retracts_future_learning_and_profile_change_does_not_transfer_it(store):
    db, root, theme = article_ready(store)
    theme = db.mutate("t", "propose", {"article_id": "a", "before": "前半。", "after": "考える。", "intent": "語尾"}, theme["revision"])
    theme = db.mutate("t", "decide", {"article_id": "a", "proposal_ids": ["p1"], "decision": "adopted", "scope": "future"}, theme["revision"])
    theme = db.mutate("t", "undo", {"article_id": "a"}, theme["revision"])
    assert not db.generation_references("other")["learning_examples"]
    theme = db.mutate("t", "redo", {"article_id": "a"}, theme["revision"])
    assert db.generation_references("other")["learning_examples"]
    (root / "voice.md").write_text("別の明示した文体")
    assert not db.generation_references("other")["learning_examples"]


def test_crlf_draft_readback_is_byte_faithful_and_not_an_external_conflict(store):
    db, root = store
    (root / "drafts").mkdir()
    raw = b"---\r\ntitle: Sample\r\n---\r\n\r\nParagraph.\r\n"
    (root / "drafts/crlf.md").write_bytes(raw)
    theme = db.create_theme("CRLF", "crlf")
    theme = db.mutate("crlf", "open_article", {"draft_path": "drafts/crlf.md"}, theme["revision"])
    assert theme["articles"][0]["draft"].encode() == raw and not theme["conflicts"]


def test_compare_then_resolve_persists_unsaved_buffer_without_implicit_overwrite(store):
    db, root, theme = article_ready(store)
    path = root / "drafts/_themes/t/a.md"
    path.write_text("外部で更新した最新稿。")
    latest = db.get_theme("t")
    sha = latest["articles"][0]["observed_draft_sha256"]
    saved = db.mutate("t", "resolve_draft", {"article_id": "a", "draft": "保持していた未保存の編集。", "expected_draft_sha256": sha}, latest["revision"])
    assert saved["articles"][0]["draft"] == "保持していた未保存の編集。"
    assert module.SessionStore(root / "settings.json").get_theme("t")["articles"][0]["draft"] == "保持していた未保存の編集。"
    record, _ = module._FEEDBACK.read_feedback_record(db._dirs, db.feedback_article_id("t", "a"))
    assert record["entries"][0]["before"] == "外部で更新した最新稿。"


def test_comparison_becomes_stale_if_disk_changes_again(store):
    db, root, theme = article_ready(store)
    sha = db.get_theme("t")["articles"][0]["observed_draft_sha256"]
    path = root / "drafts/_themes/t/a.md"; path.write_text("比較の後の変更。")
    with pytest.raises(module.SessionError) as error:
        db.mutate("t", "resolve_draft", {"article_id": "a", "draft": "古い比較に基づく編集。", "expected_draft_sha256": sha}, theme["revision"])
    assert error.value.code == "stale" and path.read_text() == "比較の後の変更。"


def test_last_moment_disk_edit_during_feedback_staging_is_not_overwritten(store, monkeypatch):
    db, root, theme = article_ready(store)
    path = root / "drafts/_themes/t/a.md"; original = db._feedback_writes
    def changed(*args, **kwargs):
        planned = original(*args, **kwargs)
        path.write_text("保存準備中の外部編集。")
        return planned
    monkeypatch.setattr(db, "_feedback_writes", changed)
    with pytest.raises(module.SessionError) as error:
        db.mutate("t", "save_draft", {"article_id": "a", "draft": "上書きしない。"}, theme["revision"])
    assert error.value.code == "external_edit" and path.read_text() == "保存準備中の外部編集。"


def test_reload_never_writes_draft(store, monkeypatch):
    db, root, theme = article_ready(store)
    draft = db._draft_path('t', 'a')
    draft.write_bytes(b'external')
    original = module._atomic
    def observe(path, data):
        assert path != draft
        return original(path, data)
    monkeypatch.setattr(module, '_atomic', observe)
    db.mutate('t', 'reload_draft', {'article_id': 'a'}, theme['revision'])


def test_initial_crash_can_recover(store, monkeypatch):
    db, root = store
    original = module._atomic
    def crash(path, data):
        if path.name == 'session.json':
            raise KeyboardInterrupt()
        return original(path, data)
    monkeypatch.setattr(module, '_atomic', crash)
    with pytest.raises(KeyboardInterrupt): db.create_theme('T', 't')
    monkeypatch.setattr(module, '_atomic', original)
    journal = db._theme_path('t').with_name('transaction.json')
    evidence = journal.read_bytes()
    with pytest.raises(module.SessionError) as error:
        db.create_theme('replacement', 't')
    assert error.value.code == 'recovery_required'
    assert journal.read_bytes() == evidence
    assert db.mutate('t', 'recover', {}, None)['recovered']
    db.create_theme('T', 't')


def test_racing_editor_bytes_survive_save_and_rollback(store, monkeypatch):
    db, root, theme = article_ready(store)
    draft = db._draft_path('t', 'a')
    original = Path.rename
    fired = False
    def race(path, target):
        nonlocal fired
        if path == draft and not fired:
            fired = True
            path.write_bytes(b'external race')
        return original(path, target)
    monkeypatch.setattr(Path, 'rename', race)
    db.mutate('t', 'save_draft', {'article_id': 'a', 'draft': 'new'}, theme['revision'])
    assert any(p.read_bytes() == b'external race' for p in draft.parent.glob('.nps-preserved-*/a.md'))


def test_exclusive_install_and_failed_restore_preserve_both_versions(store, monkeypatch):
    db, root, theme = article_ready(store)
    draft = db._draft_path('t', 'a')
    original = module.os.link
    def race(source, target):
        if Path(target) == draft:
            draft.write_bytes(b'external install')
            raise FileExistsError()
        return original(source, target)
    monkeypatch.setattr(module.os, 'link', race)
    with pytest.raises(module.SessionError):
        db.mutate('t', 'save_draft', {'article_id': 'a', 'draft': 'candidate'}, theme['revision'])
    retained = [p.read_bytes() for p in draft.parent.glob('.nps-preserved-*/*')]
    assert b'candidate' in retained
    assert b'external install' in retained or draft.read_bytes() == b'external install'
    assert db._theme_path('t').with_name('transaction.json').exists()


def test_open_inode_late_write_is_retained(store):
    db, root, theme = article_ready(store)
    draft = db._draft_path('t', 'a')
    with draft.open('r+b') as editor:
        size = len(draft.read_bytes())
        db.mutate('t', 'save_draft', {'article_id': 'a', 'draft': 'new'}, theme['revision'])
        editor.seek(0)
        editor.write(b'x' * size)
        editor.flush()
    assert draft.read_bytes() == b'new'
    assert any(p.read_bytes() == b'x' * size for p in draft.parent.glob('.nps-preserved-*/a.md'))


def test_candidate_io_failure_restores_original_exclusively(store, monkeypatch):
    db, root, theme = article_ready(store)
    draft = db._draft_path('t', 'a')
    before = draft.read_bytes()
    original = module._atomic
    def fail(path, data):
        if path.name == 'candidate':
            raise OSError('synthetic disk full')
        return original(path, data)
    monkeypatch.setattr(module, '_atomic', fail)
    with pytest.raises(module.SessionError):
        db.mutate('t', 'save_draft', {'article_id': 'a', 'draft': 'new'}, theme['revision'])
    assert draft.read_bytes() == before
    assert any(p.read_bytes() == before for p in draft.parent.glob('.nps-preserved-*/a.md'))
    assert db._theme_path('t').with_name('transaction.json').exists()
