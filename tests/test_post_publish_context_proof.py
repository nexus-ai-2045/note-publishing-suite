from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_post_publish_writes_external_ledgers_idempotently(tmp_path: Path) -> None:
    draft = tmp_path / "article.md"
    draft.write_text("# article\n", encoding="utf-8")
    ledger_dir = tmp_path / "private-ledgers"
    ledger_dir.mkdir()
    (ledger_dir / "note_drafts.json").write_text(
        json.dumps(
            [
                {
                    "draft": "content/drafts/article.md",
                    "note_id": "n123",
                    "status": "editor-draft-saved",
                }
            ]
        ),
        encoding="utf-8",
    )

    command = [
        sys.executable,
        str(ROOT / "scripts" / "post_publish.py"),
        "--url",
        "https://note.com/example/n/n123",
        "--draft",
        str(draft),
        "--title",
        "Published title",
        "--published-at",
        "2026-07-15T22:21:00+09:00",
        "--verified-at",
        "2026-07-16T06:35:03+09:00",
        "--note-id",
        "n123",
        "--verification-status",
        "published_verified",
        "--published-snapshot",
        "research/snapshots/n123.txt",
        "--published-body-sha256",
        "a" * 64,
        "--local-draft-differs-from-published",
        "--cover-image-verified",
        "--ledger-dir",
        str(ledger_dir),
        "--write-ledger",
    ]
    for _ in range(2):
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr

    published = json.loads((ledger_dir / "published_notes.json").read_text(encoding="utf-8"))
    drafts = json.loads((ledger_dir / "note_drafts.json").read_text(encoding="utf-8"))
    assert len(published) == 1
    assert published[0]["plain_status"] == "published_verified"
    assert published[0]["published_body_sha256"] == "a" * 64
    assert published[0]["cover_image_verified"] is True
    assert len(drafts) == 1
    assert drafts[0]["status"] == "published_from_note_editor_record"
    assert drafts[0]["published_title"] == "Published title"


def test_note_diff_snapshot_has_stable_hash(tmp_path: Path) -> None:
    module = load_module("note_diff_check_context_proof", ROOT / "scripts" / "note_diff_check.py")
    snapshot = tmp_path / "snapshot.txt"
    digest = module.write_snapshot("public body\n", snapshot)
    assert snapshot.read_text(encoding="utf-8") == "public body\n"
    assert digest == "a6ce45cbe1b311161389958ebe222cc5173b3b1b4824b93ab2b2429e407cd8eb"


def test_verified_publication_requires_verification_time(tmp_path: Path) -> None:
    draft = tmp_path / "article.md"
    draft.write_text("# article\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "post_publish.py"),
            "--url",
            "https://note.com/example/n/n123",
            "--draft",
            str(draft),
            "--verification-status",
            "published_verified",
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "--verified-at is required" in result.stderr


def run_ledger_cli(tmp_path: Path, *options: str):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "post_publish.py"),
         "--url", "https://note.com/example/n/n123?app_launch=false",
         "--draft", str(tmp_path / "article.md"),
         "--ledger-dir", str(tmp_path), *options],
        text=True, capture_output=True, check=False,
    )


def test_unknown_publication_time_and_default_dry_run(tmp_path: Path) -> None:
    result = run_ledger_cli(tmp_path)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["mode"] == "dry-run"
    assert output["published_entry"]["published_at"] is None
    assert output["published_entry"]["note_id"] == "n123"
    assert output["published_entry"]["url"] == "https://note.com/example/n/n123"
    assert output["published_entry"]["plain_status"] == "published_or_scheduled_unverified"
    assert not (tmp_path / "published_notes.json").exists()


def test_rejects_invalid_url_and_mismatched_id(tmp_path: Path) -> None:
    for options in [
        ("--url", "https://note.com.attacker.test/example/n/n123"),
        ("--url", "https://user@note.com/example/n/n123"),
        ("--url", "https://note.com/example/n/n123/extra"),
        ("--url", "http://note.com/example/n/n123"),
        ("--note-id", "n456"),
    ]:
        result = run_ledger_cli(tmp_path, *options, "--write-ledger")
        assert result.returncode == 2
        assert not (tmp_path / "published_notes.json").exists()


def test_distinct_article_same_basename_is_preserved(tmp_path: Path) -> None:
    rows = [
        {"draft": str(tmp_path / "article.md"), "note_id": "n456", "status": "draft"},
        {"draft": str(tmp_path / "elsewhere" / "article.md"), "status": "draft"},
    ]
    target = tmp_path / "note_drafts.json"
    target.write_text(json.dumps(rows), encoding="utf-8")
    for _ in range(2):
        result = run_ledger_cli(tmp_path, "--write-ledger")
        assert result.returncode == 0, result.stderr
    written = json.loads(target.read_text())
    assert written[:2] == rows
    assert len(written) == 3
    assert written[2]["note_id"] == "n123"
    assert len(json.loads((tmp_path / "published_notes.json").read_text())) == 1


def test_invalid_either_ledger_preserves_both_files(tmp_path: Path) -> None:
    for broken_name in ["published_notes.json", "note_drafts.json"]:
        for broken_content in ["{}", "[null]", "not-json"]:
            published = tmp_path / "published_notes.json"
            drafts = tmp_path / "note_drafts.json"
            published.write_text("[]")
            drafts.write_text("[]")
            (tmp_path / broken_name).write_text(broken_content)
            before = {p: p.read_bytes() for p in [published, drafts]}
            result = run_ledger_cli(tmp_path, "--write-ledger")
            assert result.returncode != 0
            assert {p: p.read_bytes() for p in before} == before


def test_reregister_preserves_archive_link(tmp_path):
    ledger = tmp_path / "data"
    ledger.mkdir()
    (ledger / "published_notes.json").write_text(json.dumps([{"note_id": "n123", "url": "https://note.com/example/n/n123", "archive_path": "content/published/article.md"}]))
    command = [sys.executable, str(ROOT / "scripts/post_publish.py"), "--url", "https://note.com/example/n/n123", "--draft", str(tmp_path / "article.md"), "--ledger-dir", str(ledger), "--write-ledger"]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    rows = json.loads((ledger / "published_notes.json").read_text())
    assert len(rows) == 1
    assert rows[0]["archive_path"] == "content/published/article.md"
