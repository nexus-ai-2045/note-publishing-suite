"""内部ブラウザ証跡による公開後処理の回帰検証。"""
import hashlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import post_publish as post
import sync_note_public_snapshot as sync

URL = "https://note.com/example/n/n123"


def evidence(tmp_path):
    body = "本人の本文"
    obj = {"schema": "note-public-observation/v1", "url": URL, "note_id": "n123", "title": "題",
           "body": body, "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
           "captured_at": "2026-10-05T12:00:00+09:00", "captured_by": "codex-internal-browser"}
    p = tmp_path / "observation.json"
    p.write_text(json.dumps(obj))
    return p, obj


def setup(tmp_path):
    pub = tmp_path / "data/published_notes.json"
    pub.parent.mkdir()
    pub.write_text(json.dumps([{"note_id": "n123", "url": URL, "extra": {"preserve": True}, "tags": ["既存"]}]))
    drafts = pub.with_name("note_drafts.json")
    drafts.write_text("[]")
    draft = tmp_path / "draft.md"
    draft.write_text("本人の本文")
    ev, _ = evidence(tmp_path)
    args = ["--url", URL, "--draft", str(draft), "--published-ledger", str(pub), "--draft-ledger", str(drafts), "--local-observation", str(ev)]
    return pub, drafts, draft, ev, args


def test_dry_run_and_idempotent_unknown_field_preservation(tmp_path):
    pub, drafts, _, _, args = setup(tmp_path)
    before = pub.read_bytes()
    assert post.main(args) == 0
    assert pub.read_bytes() == before and drafts.read_text() == "[]"
    post.main(args + ["--write-ledger"])
    first = pub.read_bytes(), drafts.read_bytes()
    post.main(args + ["--write-ledger"])
    assert first == (pub.read_bytes(), drafts.read_bytes())
    row = json.loads(pub.read_text())[0]
    assert row["extra"] == {"preserve": True} and row["tags"] == ["既存"]
    assert len(json.loads(drafts.read_text())) == 1


@pytest.mark.parametrize("field,value", [("url", "https://note.com/other/n/n123"), ("note_id", "n456"), ("body_sha256", "bad"), ("captured_at", "2026-10-05"), ("captured_by", "chrome")])
def test_bad_local_observation_stops_without_network(tmp_path, monkeypatch, field, value):
    pub, _, draft, ev, _ = setup(tmp_path)
    obj = json.loads(ev.read_text()); obj[field] = value; ev.write_text(json.dumps(obj))
    monkeypatch.setattr(sync, "fetch_published_note", lambda _: pytest.fail("network fallback"))
    with pytest.raises(ValueError):
        sync.main(["--url", URL, "--output", str(tmp_path / "snapshot.md"), "--source-draft", str(draft), "--ledger", str(pub), "--local-observation", str(ev)])
    assert not (tmp_path / "snapshot.md").exists()


def test_snapshot_default_dry_run_offline_and_write(tmp_path, monkeypatch):
    pub, _, draft, ev, _ = setup(tmp_path)
    monkeypatch.setattr(sync, "fetch_published_note", lambda _: pytest.fail("network called"))
    out = tmp_path / "content/published/article.md"
    args = ["--url", URL, "--output", str(out), "--source-draft", str(draft), "--ledger", str(pub), "--local-observation", str(ev)]
    sync.main(args)
    assert not out.exists()
    sync.main(args + ["--write-ledger"])
    assert "codex-internal-browser" in out.read_text()
    assert json.loads(pub.read_text())[0]["archive_path"] == "content/published/article.md"


def test_invalid_ledger_and_missing_draft_stop_before_write(tmp_path):
    pub, drafts, draft, _, args = setup(tmp_path)
    pub.write_text("{}")
    with pytest.raises(ValueError): post.main(args + ["--write-ledger"])
    assert drafts.read_text() == "[]"
    draft.unlink()
    with pytest.raises(ValueError): post.main(args)


def test_interrupted_two_ledger_commit_recovers(tmp_path, monkeypatch):
    pub, drafts, _, _, args = setup(tmp_path)
    real_write = post.write_list
    def fail_draft(path, rows):
        if path == drafts:
            raise OSError("interrupted")
        real_write(path, rows)
    monkeypatch.setattr(post, "write_list", fail_draft)
    with pytest.raises(OSError, match="interrupted"):
        post.main(args + ["--write-ledger"])
    assert post.transaction_path(pub).exists()
    monkeypatch.setattr(post, "write_list", real_write)
    post.main(args + ["--write-ledger"])
    assert len(json.loads(pub.read_text())) == 1
    assert len(json.loads(drafts.read_text())) == 1
    assert not post.transaction_path(pub).exists()


def test_transaction_different_draft_target_stops(tmp_path):
    pub, drafts, _, _, _ = setup(tmp_path)
    payload = {"schema": "note-ledger-transaction/v1", "published_path": str(pub.resolve()),
               "draft_path": str((tmp_path / "other.json").resolve()), "published": [], "drafts": []}
    post.transaction_path(pub).write_text(json.dumps(payload))
    before = pub.read_bytes(), drafts.read_bytes()
    with pytest.raises(ValueError):
        post.recover_transaction(pub, drafts)
    assert before == (pub.read_bytes(), drafts.read_bytes())


def test_snapshot_never_overwrites_source_alias(tmp_path, monkeypatch):
    pub, _, draft, ev, _ = setup(tmp_path)
    before = draft.read_bytes()
    alias = tmp_path / "source-alias.md"
    alias.symlink_to(draft)
    monkeypatch.setattr(sync, "fetch_published_note", lambda _: pytest.fail("network called"))
    with pytest.raises(ValueError, match="別ファイル"):
        sync.main(["--url", URL, "--output", str(alias), "--source-draft", str(draft),
                   "--ledger", str(pub), "--local-observation", str(ev), "--write-ledger"])
    assert draft.read_bytes() == before


def test_same_archive_link_written_to_both_ledgers(tmp_path):
    pub, drafts, _, _, args = setup(tmp_path)
    snapshot = tmp_path / "content/published/public.md"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("公開本文")
    post.main(args + ["--archive-path", "content/published/public.md", "--write-ledger"])
    assert json.loads(pub.read_text())[0]["archive_path"] == "content/published/public.md"
    assert json.loads(drafts.read_text())[0]["archive_path"] == "content/published/public.md"


@pytest.mark.parametrize('source', ['draft', 'observation', 'snapshot'])
@pytest.mark.parametrize('target', ['published', 'drafts', 'journal'])
@pytest.mark.parametrize('alias', ['same', 'symlink', 'hardlink'])
def test_post_inputs_never_alias_outputs(tmp_path, source, target, alias):
    pub, drafts, draft, ev, args = setup(tmp_path)
    snapshot = tmp_path / 'snapshot.md'
    snapshot.write_text('公開本文')
    origin = {'draft': draft, 'observation': ev, 'snapshot': snapshot}[source]
    destination = {'published': pub, 'drafts': drafts, 'journal': post.transaction_path(pub)}[target]
    if alias == 'same':
        destination = origin
    else:
        destination.unlink(missing_ok=True)
        if alias == 'symlink':
            destination.symlink_to(origin)
        else:
            destination.hardlink_to(origin)
    before = origin.read_bytes()
    args += ['--published-snapshot', str(snapshot)]
    if target != 'journal':
        flag = '--published-ledger' if target == 'published' else '--draft-ledger'
        args[args.index(flag) + 1] = str(destination)
    elif alias == 'same':
        # journal の既定パスに原稿を置き、開始前検査を通す。
        journal = post.transaction_path(pub)
        journal.write_bytes(origin.read_bytes())
        flag = {'draft': '--draft', 'observation': '--local-observation', 'snapshot': '--published-snapshot'}[source]
        args[args.index(flag) + 1] = str(journal)
    with pytest.raises(ValueError, match='別ファイル'):
        post.main(args + ['--write-ledger'])
    assert origin.read_bytes() == before


@pytest.mark.parametrize('collision', ['ledger-source', 'ledger-observation', 'output-ledger', 'output-journal', 'ledger-journal'])
def test_snapshot_rejects_all_output_aliases_before_fetch(tmp_path, monkeypatch, collision):
    pub, _, draft, ev, _ = setup(tmp_path)
    out = tmp_path / 'snapshot.md'
    ledger = pub
    if collision == 'ledger-source': draft = pub
    if collision == 'ledger-observation': ev = pub
    if collision == 'output-ledger': out = pub
    if collision == 'output-journal': out = sync.transaction_path(pub)
    if collision == 'ledger-journal': sync.transaction_path(pub).hardlink_to(pub)
    before = pub.read_bytes()
    monkeypatch.setattr(sync, 'fetch_published_note', lambda _: pytest.fail('network called'))
    with pytest.raises(ValueError, match='別ファイル'):
        sync.main(['--url', URL, '--output', str(out), '--source-draft', str(draft),
                   '--ledger', str(ledger), '--local-observation', str(ev), '--write-ledger'])
    assert pub.read_bytes() == before


def test_post_rejects_invalid_hash_before_mutation(tmp_path):
    pub, drafts, _, _, args = setup(tmp_path)
    before = pub.read_bytes(), drafts.read_bytes()
    with pytest.raises(ValueError, match='SHA-256'):
        post.main(args + ['--published-body-sha256', 'not-a-hash', '--write-ledger'])
    assert before == (pub.read_bytes(), drafts.read_bytes())


@pytest.mark.parametrize('protected', ['draft', 'observation', 'ledger', 'journal'])
def test_pending_snapshot_recovery_preserves_protected_input(tmp_path, protected):
    pub, _, draft, ev, _ = setup(tmp_path)
    out = tmp_path / 'content/published/snapshot.md'
    # 正常なdry-run出力から、整合した旧journalを作る。
    import io
    from contextlib import redirect_stdout
    captured = io.StringIO()
    with redirect_stdout(captured):
        sync.main(['--url', URL, '--output', str(out), '--source-draft', str(draft),
                   '--ledger', str(pub), '--local-observation', str(ev)])
    dry = json.loads(captured.getvalue())
    journal = sync.transaction_path(pub)
    target = {'draft': draft, 'observation': ev, 'ledger': pub, 'journal': journal}[protected]
    payload = {'schema': 'note-public-snapshot-transaction/v1', 'note_id': 'n123',
               'archive_path': target.relative_to(tmp_path).as_posix(), 'title': dry['title'],
               'body_char_count': dry['body_char_count'], 'body_sha256': dry['public_body_sha256'],
               'snapshot_text': dry['snapshot_text']}
    journal.write_text(json.dumps(payload))
    before = target.read_bytes(), pub.read_bytes(), journal.read_bytes()
    with pytest.raises(ValueError, match='別ファイル'):
        sync.main(['--url', URL, '--output', str(out), '--source-draft', str(draft),
                   '--ledger', str(pub), '--local-observation', str(ev), '--write-ledger'])
    assert before == (target.read_bytes(), pub.read_bytes(), journal.read_bytes())
    assert not out.exists()
