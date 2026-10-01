from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    sys.path.insert(0, str(path.parent))
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


def test_published_update_verifies_live_api_fields_without_draft() -> None:
    module = load_module("verify_published_update", ROOT / "scripts" / "verify_published_update.py")
    data = {
        "status": "published", "key": "nabc123", "user": {"urlname": "example"},
        "name": "Example title", "eyecatch": "https://assets.example/cover.png",
        "publish_at": "2026-01-02T03:04:05+09:00",
        "body": "<p>Updated sentence</p><p>Other text</p>",
    }
    result = module.verify(
        data, url="https://note.com/example/n/nabc123", expected_title="Example title",
        expected_eyecatch_url="https://assets.example/cover.png",
        contains=["Updated sentence"], absent=["Old sentence"],
    )
    assert result["overall"] == "ok"
    assert result["checks"]["owner_matches"] is True
    assert result["checks"]["eyecatch_matches"] is True
    assert result["body_sha256"]


def test_published_update_blocks_wrong_asset_or_owner() -> None:
    module = load_module("verify_published_update_failed", ROOT / "scripts" / "verify_published_update.py")
    data = {
        "status": "published", "key": "nabc123", "user": {"urlname": "other"},
        "name": "Example title", "eyecatch": "https://assets.example/old.png",
        "body": "<p>Old sentence</p>",
    }
    result = module.verify(
        data, url="https://note.com/example/n/nabc123", expected_title="Example title",
        expected_eyecatch_url="https://assets.example/new.png",
        contains=["Updated sentence"], absent=["Old sentence"],
    )
    assert result["overall"] == "blocked"
    assert result["checks"]["owner_matches"] is False
    assert result["checks"]["eyecatch_matches"] is False
    assert result["checks"]["contains_phrases"]["Updated sentence"] is False
    assert result["checks"]["absent_phrases"]["Old sentence"] is False


def test_published_update_accepts_transform_query_for_same_asset() -> None:
    module = load_module("verify_published_update_transform", ROOT / "scripts" / "verify_published_update.py")
    data = {
        "status": "published", "key": "nabc123", "user": {"urlname": "example"},
        "name": "Example title",
        "eyecatch": "https://assets.example/cover-id.png?fit=bounds&quality=85&width=1280",
        "body": "<p>Updated sentence</p>",
    }
    result = module.verify(
        data, url="https://note.com/example/n/nabc123", expected_title="Example title",
        expected_eyecatch_url="https://assets.example/cover-id.png",
        contains=["Updated sentence"], absent=[],
    )
    assert result["overall"] == "ok"
    assert result["checks"]["eyecatch_matches"] is True
    assert result["eyecatch_url"] == data["eyecatch"]


def test_published_update_rejects_different_asset_and_userinfo() -> None:
    module = load_module("verify_published_update_asset", ROOT / "scripts" / "verify_published_update.py")
    expected = "https://assets.example/cover-id.png"
    assert module.image_asset_identity("https://attacker@assets.example/cover-id.png") is None
    data = {
        "status": "published", "key": "nabc123", "user": {"urlname": "example"},
        "name": "Example title", "eyecatch": "https://assets.example/other-id.png?width=1280",
        "body": "<p>Updated sentence</p>",
    }
    result = module.verify(
        data, url="https://note.com/example/n/nabc123", expected_title="Example title",
        expected_eyecatch_url=expected, contains=[], absent=[],
    )
    assert result["overall"] == "blocked"
    assert result["checks"]["eyecatch_matches"] is False
    assert module.image_asset_identity("https://other.example/cover-id.png") != module.image_asset_identity(expected)


def test_published_update_ledger_requires_one_current_row() -> None:
    module = load_module("verify_published_update_ledger", ROOT / "scripts" / "verify_published_update.py")
    live = {
        "url": "https://note.com/example/n/nabc123", "note_id": "nabc123",
        "title": "Example title", "eyecatch_url": "https://assets.example/cover-id.png?width=1280",
        "body_sha256": "a" * 64,
    }
    row = {
        "url": live["url"], "note_id": live["note_id"], "title": live["title"],
        "image_url": "https://assets.example/cover-id.png", "plain_status": "published_verified",
        "published_body_sha256": live["body_sha256"],
    }
    assert module.verify_ledger([row], live=live)["overall"] == "ok"
    private_row = row | {"plain_status": "公開ページと照合済み", "status": "published",
                         "verification_status": "published_verified"}
    assert module.verify_ledger([private_row], live=live)["overall"] == "ok"
    private_alias = {key: value for key, value in private_row.items() if key != "published_body_sha256"}
    private_alias["public_body_sha256"] = live["body_sha256"]
    assert module.verify_ledger([private_alias], live=live)["overall"] == "ok"
    assert module.verify_ledger([private_alias | {"published_body_sha256": "b" * 64}], live=live)["overall"] == "blocked"
    assert module.verify_ledger([row | {"verification_status": "unverified"}], live=live)["overall"] == "blocked"
    assert module.verify_ledger([row | {"status": "draft"}], live=live)["overall"] == "blocked"
    assert module.verify_ledger([], live=live)["overall"] == "blocked"
    assert module.verify_ledger([row, row], live=live)["overall"] == "blocked"
    assert module.verify_ledger([row | {"image_url": "https://assets.example/other-id.png"}], live=live)["overall"] == "blocked"
    assert module.verify_ledger([row | {"published_body_sha256": "b" * 64}], live=live)["overall"] == "blocked"
    assert module.verify_ledger([{key: value for key, value in row.items() if key != "published_body_sha256"}], live=live)["overall"] == "blocked"
    assert module.verify_ledger([private_row | {"verification_status": "unverified"}], live=live)["overall"] == "blocked"


def test_published_update_rejects_nonpublic_url() -> None:
    module = load_module("verify_published_update_url", ROOT / "scripts" / "verify_published_update.py")
    import pytest

    with pytest.raises(ValueError):
        module.parse_note_url("http://localhost/example/n/nabc123")
