"""sync_note_public_snapshot.py の台帳結線 (join) のテスト。

`archive_path` は台帳の行とアーカイブ実体を繋ぐ唯一の参照。
これを人が手で書いていたため、隣の行へ書き込む事故が起きた
（記事Bのパスが記事Aの行に入る取り違えを防ぐ）。
行の選択を note_id による機械的一致に固定し、該当行が無ければ
書かずに失敗させる。DB の外部キー制約に相当する振る舞い。
"""

from __future__ import annotations

import json
import os
import stat
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_note_public_snapshot as sync  # noqa: E402


def _ledger(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "data" / "published_notes.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


ROWS = [
    {"note_id": "n111111111111", "url": "https://note.com/example/n/n111111111111",
     "title": "記事A", "archive_path": None},
    {"note_id": "n222222222222", "url": "https://note.com/example/n/n222222222222",
     "title": "記事B", "archive_path": None},
]


def test_extract_note_id_from_url():
    assert sync.extract_note_id("https://note.com/example/n/n222222222222") == "n222222222222"


def test_extract_note_id_rejects_non_note_url():
    with pytest.raises(ValueError):
        sync.extract_note_id("https://example.com/foo")


def test_wire_archive_path_updates_only_the_matching_row(tmp_path):
    """note_id で行を選ぶ。隣の行は絶対に触らない。"""
    ledger = _ledger(tmp_path, [dict(r) for r in ROWS])

    sync.wire_archive_path(ledger, "n222222222222", "content/published/article-b.md")

    rows = json.loads(ledger.read_text(encoding="utf-8"))
    assert rows[0]["archive_path"] is None, "隣の行 (記事A) が書き換わってはいけない"
    assert rows[1]["archive_path"] == "content/published/article-b.md"


def test_wire_archive_path_rejects_unknown_note_id(tmp_path):
    """台帳に無い note_id は書かずに失敗する (外部キー制約の代わり)。"""
    ledger = _ledger(tmp_path, [dict(r) for r in ROWS])
    before = ledger.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="n0000000000000"):
        sync.wire_archive_path(ledger, "n0000000000000", "content/published/x.md")

    assert ledger.read_text(encoding="utf-8") == before, "失敗時に台帳を書き換えてはいけない"


def test_wire_archive_path_rejects_duplicate_note_id(tmp_path):
    """同じ note_id が複数行あると、どちらへ書くか機械的に決まらないので失敗させる。"""
    ledger = _ledger(tmp_path, [dict(ROWS[1]), dict(ROWS[1])])

    with pytest.raises(ValueError):
        sync.wire_archive_path(ledger, "n222222222222", "content/published/article-b.md")


def test_wire_archive_path_is_idempotent(tmp_path):
    """同じ値を二度書いても壊れない。"""
    ledger = _ledger(tmp_path, [dict(r) for r in ROWS])

    sync.wire_archive_path(ledger, "n222222222222", "content/published/article-b.md")
    first = ledger.read_text(encoding="utf-8")
    sync.wire_archive_path(ledger, "n222222222222", "content/published/article-b.md")

    assert ledger.read_text(encoding="utf-8") == first


def test_wire_public_snapshot_metadata_updates_only_public_owned_fields(tmp_path):
    """公開現物由来の値を一括更新し、reaction_tracking 等の未知fieldは保持する。"""
    rows = [dict(ROWS[1], reaction_tracking={"status": "active"}, custom="keep")]
    ledger = _ledger(tmp_path, rows)

    sync.wire_public_snapshot_metadata(
        ledger,
        "n222222222222",
        "content/published/article-b.md",
        title="公開タイトル v2",
        body_char_count=123,
        body_sha256="a" * 64,
    )

    row = json.loads(ledger.read_text(encoding="utf-8"))[0]
    assert row["archive_path"] == "content/published/article-b.md"
    assert row["title"] == "公開タイトル v2"
    assert row["body_char_count"] == 123
    assert row["public_body_sha256"] == "a" * 64
    assert row["reaction_tracking"] == {"status": "active"}
    assert row["custom"] == "keep"


def test_wire_public_snapshot_metadata_fails_closed_on_concurrent_writer(tmp_path):
    ledger = _ledger(tmp_path, [dict(ROWS[1])])
    before = ledger.read_bytes()

    with sync.ledger_file_lock(ledger):
        with pytest.raises(RuntimeError, match="別processが更新中"):
            sync.wire_public_snapshot_metadata(
                ledger,
                "n222222222222",
                "content/published/article-b.md",
                title="競合タイトル",
            )

    assert ledger.read_bytes() == before


def test_atomic_write_preserves_existing_file_mode(tmp_path):
    target = tmp_path / "snapshot.md"
    target.write_text("old", encoding="utf-8")
    target.chmod(0o640)

    sync.atomic_write_bytes(target, b"new")

    assert target.read_bytes() == b"new"
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_archive_rel_path_is_repo_relative_posix(tmp_path):
    """台帳に書く値は repo 相対 POSIX 形式。Windows の区切りを混ぜない。"""
    ledger = _ledger(tmp_path, [dict(r) for r in ROWS])
    output = tmp_path / "content" / "published" / "article-b.md"

    rel = sync.archive_rel_path(ledger, output)

    assert rel == "content/published/article-b.md"


def test_parser_accepts_optional_ledger():
    """--ledger は parser 上は任意。省略時の解決は resolve_ledger_path が担う。"""
    args = sync.build_parser().parse_args(
        ["--url", "https://note.com/example/n/n222222222222", "--title", "t",
         "--output", "o.md", "--source-draft", "d.md"]
    )
    assert args.ledger is None


def test_parser_accepts_omitted_title_because_public_api_is_canonical():
    args = sync.build_parser().parse_args(
        ["--url", "https://note.com/example/n/n222222222222",
         "--output", "o.md", "--source-draft", "d.md"]
    )
    assert args.title is None


def test_main_uses_public_title_and_updates_snapshot_metadata(tmp_path, monkeypatch, capsys):
    ledger = _ledger(tmp_path, [dict(ROWS[1], reaction_tracking={"status": "active"})])
    output = tmp_path / "content" / "published" / "article-b.md"
    monkeypatch.setattr(
        sync,
        "fetch_published_note",
        lambda _url: {"title": "公開タイトル v2", "body": "公開本文"},
    )

    code = sync.main(["--write-ledger",
        "--url", ROWS[1]["url"],
        "--title", "古い手入力タイトル",
        "--output", str(output),
        "--source-draft", str(Path(__file__)),
        "--ledger", str(ledger),
    ])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["title"] == "公開タイトル v2"
    assert payload["requested_title_matched"] is False
    row = json.loads(ledger.read_text(encoding="utf-8"))[0]
    assert row["title"] == "公開タイトル v2"
    assert row["body_char_count"] == len("公開本文")
    assert row["reaction_tracking"] == {"status": "active"}
    assert row["public_body_sha256"] == payload["public_body_sha256"]
    snapshot = output.read_text(encoding="utf-8")
    assert "# 公開タイトル v2" in snapshot
    assert "body_sha256:" in snapshot


def test_main_rolls_back_snapshot_when_ledger_write_fails(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, [dict(ROWS[1])])
    before_ledger = ledger.read_bytes()
    output = tmp_path / "content" / "published" / "article-b.md"
    output.parent.mkdir(parents=True)
    output.write_text("以前のsnapshot\n", encoding="utf-8")
    monkeypatch.setattr(
        sync,
        "fetch_published_note",
        lambda _url: {"title": "公開タイトル v2", "body": "公開本文"},
    )
    monkeypatch.setattr(
        sync,
        "wire_public_snapshot_metadata",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("ledger write failed")),
    )

    with pytest.raises(OSError, match="ledger write failed"):
        sync.main(["--write-ledger",
            "--url", ROWS[1]["url"],
            "--output", str(output),
            "--source-draft", str(Path(__file__)),
            "--ledger", str(ledger),
        ])

    assert output.read_text(encoding="utf-8") == "以前のsnapshot\n"
    assert ledger.read_bytes() == before_ledger
    assert not sync.transaction_path(ledger).exists()


def test_interrupted_transaction_is_forward_completed_on_next_run(tmp_path, monkeypatch):
    """BaseException 中断ではjournalを残し、次回lock内でsnapshot/ledgerを同じ状態へ揃える。"""
    ledger = _ledger(tmp_path, [dict(ROWS[1], reaction_tracking={"status": "active"})])
    output = tmp_path / "content" / "published" / "article-b.md"
    output.parent.mkdir(parents=True)
    output.write_text("以前のsnapshot\n", encoding="utf-8")
    monkeypatch.setattr(
        sync,
        "fetch_published_note",
        lambda _url: {"title": "公開タイトル v2", "body": "公開本文"},
    )
    original_wire = sync.wire_public_snapshot_metadata

    def interrupt_before_ledger(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(sync, "wire_public_snapshot_metadata", interrupt_before_ledger)
    with pytest.raises(KeyboardInterrupt):
        sync.main(["--write-ledger",
            "--url", ROWS[1]["url"],
            "--output", str(output),
            "--source-draft", str(Path(__file__)),
            "--ledger", str(ledger),
        ])

    journal = sync.transaction_path(ledger)
    assert journal.exists()
    assert "公開本文" in output.read_text(encoding="utf-8")
    assert json.loads(ledger.read_text(encoding="utf-8"))[0]["archive_path"] is None

    monkeypatch.setattr(sync, "wire_public_snapshot_metadata", original_wire)
    with sync.ledger_file_lock(ledger):
        assert sync.recover_pending_transaction(ledger) is True

    row = json.loads(ledger.read_text(encoding="utf-8"))[0]
    assert row["archive_path"] == "content/published/article-b.md"
    assert row["title"] == "公開タイトル v2"
    assert row["body_char_count"] == len("公開本文")
    assert row["reaction_tracking"] == {"status": "active"}
    assert not journal.exists()


def test_recovery_rejects_invalid_journal_without_touching_state(tmp_path):
    ledger = _ledger(tmp_path, [dict(ROWS[1])])
    before = ledger.read_bytes()
    journal = sync.transaction_path(ledger)
    journal.write_text('{"schema":"wrong"}\n', encoding="utf-8")

    with sync.ledger_file_lock(ledger):
        with pytest.raises(ValueError, match="journal が不正"):
            sync.recover_pending_transaction(ledger)

    assert ledger.read_bytes() == before
    assert journal.exists(), "不正journalは証拠として残し、暗黙破棄しない"


def test_recovery_validates_ledger_row_before_writing_snapshot(tmp_path):
    ledger = _ledger(tmp_path, [dict(ROWS[1])])
    before = ledger.read_bytes()
    output = tmp_path / "content" / "published" / "unknown.md"
    body = "公開本文"
    body_hash = sync.hashlib.sha256(body.encode("utf-8")).hexdigest()
    snapshot = (
        "---\nschema_version: note-public-snapshot/v1\n"
        'title: "公開タイトル"\nsource_url: "https://note.com/example/n/n0000000000000"\n'
        "source_kind: public_note\n"
        f"body_sha256: {body_hash}\n---\n\n# 公開タイトル\n\n{body}\n"
    )
    payload = {
        "schema": "note-public-snapshot-transaction/v1",
        "note_id": "n0000000000000",
        "archive_path": "content/published/unknown.md",
        "title": "公開タイトル",
        "body_char_count": len(body),
        "body_sha256": body_hash,
        "snapshot_text": snapshot,
    }
    journal = sync.transaction_path(ledger)
    journal.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with sync.ledger_file_lock(ledger):
        with pytest.raises(ValueError, match="n0000000000000"):
            sync.recover_pending_transaction(ledger)

    assert not output.exists()
    assert ledger.read_bytes() == before
    assert journal.exists()


def test_recovery_rejects_snapshot_metadata_mismatch_before_writing(tmp_path):
    ledger = _ledger(tmp_path, [dict(ROWS[1])])
    output = tmp_path / "content" / "published" / "article-b.md"
    output.parent.mkdir(parents=True)
    output.write_text("以前のsnapshot\n", encoding="utf-8")
    body = "公開本文"
    actual_hash = sync.hashlib.sha256(body.encode("utf-8")).hexdigest()
    payload = {
        "schema": "note-public-snapshot-transaction/v1",
        "note_id": ROWS[1]["note_id"],
        "archive_path": "content/published/article-b.md",
        "title": "公開タイトル",
        "body_char_count": len(body) + 1,
        "body_sha256": actual_hash,
        "snapshot_text": (
            "---\nschema_version: note-public-snapshot/v1\n"
            f'title: "公開タイトル"\nsource_url: "{ROWS[1]["url"]}"\n'
            "source_kind: public_note\n"
            f"body_sha256: {actual_hash}\n---\n\n# 公開タイトル\n\n{body}\n"
        ),
    }
    journal = sync.transaction_path(ledger)
    journal.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with sync.ledger_file_lock(ledger):
        with pytest.raises(ValueError, match="metadata"):
            sync.recover_pending_transaction(ledger)

    assert output.read_text(encoding="utf-8") == "以前のsnapshot\n"
    assert journal.exists()


def test_recovery_rejects_frontmatter_identity_mismatch(tmp_path):
    ledger = _ledger(tmp_path, [dict(ROWS[1])])
    output = tmp_path / "content" / "published" / "article-b.md"
    body = "公開本文"
    body_hash = sync.hashlib.sha256(body.encode("utf-8")).hexdigest()
    payload = {
        "schema": "note-public-snapshot-transaction/v1",
        "note_id": ROWS[1]["note_id"],
        "archive_path": "content/published/article-b.md",
        "title": "公開タイトル",
        "body_char_count": len(body),
        "body_sha256": body_hash,
        "snapshot_text": (
            "---\nschema_version: note-public-snapshot/v1\n"
            'title: "別タイトル"\n'
            'source_url: "https://note.com/example/n/n111111111111"\n'
            "source_kind: public_note\n"
            f"body_sha256: {body_hash}\n---\n\n# 公開タイトル\n\n{body}\n"
        ),
    }
    journal = sync.transaction_path(ledger)
    journal.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with sync.ledger_file_lock(ledger):
        with pytest.raises(ValueError, match="metadata"):
            sync.recover_pending_transaction(ledger)

    assert not output.exists()
    assert json.loads(ledger.read_text(encoding="utf-8"))[0]["archive_path"] is None
    assert journal.exists()


def test_cleanup_failure_keeps_committed_state_and_journal_for_recovery(tmp_path, monkeypatch):
    """台帳commit後のjournal削除失敗では新版を戻さず、次回の冪等回復へ渡す。"""
    ledger = _ledger(tmp_path, [dict(ROWS[1])])
    output = tmp_path / "content" / "published" / "article-b.md"
    output.parent.mkdir(parents=True)
    output.write_text("以前のsnapshot\n", encoding="utf-8")
    monkeypatch.setattr(
        sync,
        "fetch_published_note",
        lambda _url: {"title": "公開タイトル v2", "body": "公開本文"},
    )
    journal = sync.transaction_path(ledger)
    original_unlink = Path.unlink

    def fail_journal_cleanup(path, *args, **kwargs):
        if path == journal:
            raise OSError("journal cleanup failed")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_journal_cleanup)
    with pytest.raises(OSError, match="journal cleanup failed"):
        sync.main(["--write-ledger",
            "--url", ROWS[1]["url"],
            "--output", str(output),
            "--source-draft", str(Path(__file__)),
            "--ledger", str(ledger),
        ])

    row = json.loads(ledger.read_text(encoding="utf-8"))[0]
    assert row["title"] == "公開タイトル v2"
    assert "公開本文" in output.read_text(encoding="utf-8")
    assert journal.exists()

    monkeypatch.setattr(Path, "unlink", original_unlink)
    with sync.ledger_file_lock(ledger):
        assert sync.recover_pending_transaction(ledger) is True
    assert not journal.exists()


def test_output_directory_fsync_failure_keeps_journal_for_recovery(tmp_path, monkeypatch):
    """replace後のdurability失敗を未書込み扱いせず、journalからforward-completeする。"""
    ledger = _ledger(tmp_path, [dict(ROWS[1])])
    output = tmp_path / "content" / "published" / "article-b.md"
    output.parent.mkdir(parents=True)
    output.write_text("以前のsnapshot\n", encoding="utf-8")
    monkeypatch.setattr(
        sync,
        "fetch_published_note",
        lambda _url: {"title": "公開タイトル v2", "body": "公開本文"},
    )
    original_fsync_directory = sync.fsync_directory
    failed = False

    def fail_output_directory_once(path):
        nonlocal failed
        if path == output.parent and not failed:
            failed = True
            raise OSError("directory fsync failed")
        return original_fsync_directory(path)

    monkeypatch.setattr(sync, "fsync_directory", fail_output_directory_once)
    with pytest.raises(sync.AtomicReplaceDurabilityError):
        sync.main(["--write-ledger",
            "--url", ROWS[1]["url"],
            "--output", str(output),
            "--source-draft", str(Path(__file__)),
            "--ledger", str(ledger),
        ])

    journal = sync.transaction_path(ledger)
    assert journal.exists()
    assert "公開本文" in output.read_text(encoding="utf-8")
    assert json.loads(ledger.read_text(encoding="utf-8"))[0]["archive_path"] is None

    monkeypatch.setattr(sync, "fsync_directory", original_fsync_directory)
    with sync.ledger_file_lock(ledger):
        assert sync.recover_pending_transaction(ledger) is True
    assert json.loads(ledger.read_text(encoding="utf-8"))[0]["title"] == "公開タイトル v2"
    assert not journal.exists()


def test_main_does_not_rollback_another_writer_when_lock_is_busy(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path, [dict(ROWS[1])])
    output = tmp_path / "content" / "published" / "article-b.md"
    output.parent.mkdir(parents=True)
    output.write_text("old\n", encoding="utf-8")
    monkeypatch.setattr(
        sync,
        "fetch_published_note",
        lambda _url: {"title": "公開タイトル v2", "body": "公開本文"},
    )

    @contextmanager
    def busy_lock(_ledger):
        output.write_text("concurrent-writer-new\n", encoding="utf-8")
        raise RuntimeError("published_notes ledger を別processが更新中です")
        yield

    monkeypatch.setattr(sync, "ledger_file_lock", busy_lock)

    with pytest.raises(RuntimeError, match="別processが更新中"):
        sync.main(["--write-ledger",
            "--url", ROWS[1]["url"],
            "--output", str(output),
            "--source-draft", str(Path(__file__)),
            "--ledger", str(ledger),
        ])

    assert output.read_text(encoding="utf-8") == "concurrent-writer-new\n"


def test_resolve_ledger_path_prefers_explicit(tmp_path):
    explicit = tmp_path / "custom.json"
    explicit.write_text("[]", encoding="utf-8")
    assert sync.resolve_ledger_path(explicit) == explicit


def test_resolve_ledger_path_uses_cwd_default(tmp_path, monkeypatch):
    """--ledger 省略時は workspace (cwd) の data/published_notes.json を使う。"""
    ledger = tmp_path / "data" / "published_notes.json"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    resolved = sync.resolve_ledger_path(None)

    assert resolved == ledger


def test_resolve_ledger_path_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sync, "PACKAGE_ROOT", tmp_path / "missing-package")

    assert sync.resolve_ledger_path(None) is None


def test_archive_rel_path_rejects_output_outside_repo(tmp_path):
    """repo 外 output は書き込み前に ValueError。孤児ファイルを作らない。"""
    ledger = _ledger(tmp_path, [dict(r) for r in ROWS])
    outside = tmp_path.parent / "outside-of-repo.md"

    with pytest.raises(ValueError, match="repo root 外"):
        sync.archive_rel_path(ledger, outside)
