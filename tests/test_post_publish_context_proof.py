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
