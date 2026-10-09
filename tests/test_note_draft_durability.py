from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "note_draft_durability.py"
SPEC = importlib.util.spec_from_file_location("note_draft_durability", SCRIPT)
assert SPEC and SPEC.loader
durability = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = durability
SPEC.loader.exec_module(durability)


def test_snapshot_verify_and_restore_missing_original(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    draft = repo / "content" / "drafts" / "日本語.md"
    draft.parent.mkdir(parents=True)
    draft.write_text("本文\n", encoding="utf-8")
    backup = tmp_path / "backup"

    snap = durability.snapshot(draft, backup, reason="manual", repo_root=repo)
    receipt = Path(snap["receipt"])
    assert snap["status"] == "verified"
    assert Path(snap["blob"]).read_bytes() == draft.read_bytes()
    assert durability.verify(receipt)["status"] == "verified"

    draft.unlink()
    status = durability.status(draft, backup, repo_root=repo)
    assert status["status"] == "missing"
    assert status["covered"] is True

    restored = durability.restore(
        receipt, draft, restore_missing_original=True
    )
    assert restored["status"] == "restored"
    assert draft.read_text(encoding="utf-8") == "本文\n"


def test_snapshot_deduplicates_blob_but_creates_receipts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    draft = repo / "draft.md"
    repo.mkdir()
    draft.write_text("same", encoding="utf-8")
    backup = tmp_path / "backup"

    first = durability.snapshot(draft, backup, reason="before_edit", repo_root=repo)
    second = durability.snapshot(draft, backup, reason="after_edit", repo_root=repo)
    assert first["blob"] == second["blob"]
    assert first["receipt"] != second["receipt"]


@pytest.mark.parametrize("name", ["empty.md", "draft.exe"])
def test_snapshot_rejects_unsafe_input(tmp_path: Path, name: str) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / name
    draft.write_bytes(b"" if name.endswith(".md") else b"x")
    with pytest.raises(durability.BoundaryError):
        durability.snapshot(draft, tmp_path / "backup", reason="manual", repo_root=repo)


def test_snapshot_rejects_backup_inside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("x", encoding="utf-8")
    with pytest.raises(durability.BoundaryError):
        durability.snapshot(draft, repo / ".backup", reason="manual", repo_root=repo)


def test_snapshot_rejects_source_outside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = tmp_path / "outside.md"
    draft.write_text("x", encoding="utf-8")
    with pytest.raises(durability.BoundaryError):
        durability.snapshot(draft, tmp_path / "backup", reason="manual", repo_root=repo)


def test_verify_detects_blob_tampering(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("safe", encoding="utf-8")
    snap = durability.snapshot(draft, tmp_path / "backup", reason="manual", repo_root=repo)
    Path(snap["blob"]).write_text("tampered", encoding="utf-8")
    result = durability.verify(Path(snap["receipt"]))
    assert result["status"] == "failed"
    assert result["error"] == "blob_hash_mismatch"


def test_restore_refuses_existing_destination_without_expected_hash(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("v1", encoding="utf-8")
    snap = durability.snapshot(draft, tmp_path / "backup", reason="manual", repo_root=repo)
    draft.write_text("v2", encoding="utf-8")
    with pytest.raises(durability.BoundaryError):
        durability.restore(Path(snap["receipt"]), draft)


def test_restore_refuses_existing_destination_even_with_expected_hash(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("v1", encoding="utf-8")
    snap = durability.snapshot(draft, tmp_path / "backup", reason="manual", repo_root=repo)
    expected = durability._sha256(draft.read_bytes())
    with pytest.raises(durability.BoundaryError, match="existing_destination_restore_not_supported"):
        durability.restore(Path(snap["receipt"]), draft, expected_current_sha256=expected)


def test_restore_does_not_replace_destination_created_during_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("backup", encoding="utf-8")
    snap = durability.snapshot(draft, tmp_path / "backup", reason="manual", repo_root=repo)
    destination = repo / "restored.md"
    original_link = durability.os.link

    def competing_link(source: str, target: Path) -> None:
        Path(target).write_text("competitor", encoding="utf-8")
        original_link(source, target)

    monkeypatch.setattr(durability.os, "link", competing_link)
    with pytest.raises(durability.BoundaryError, match="existing_destination_restore_not_supported"):
        durability.restore(Path(snap["receipt"]), destination)
    assert destination.read_text(encoding="utf-8") == "competitor"
    assert not list(destination.parent.glob(".tmp_restore_*"))


def test_restore_rejects_mocked_windows_reparse_destination_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("backup", encoding="utf-8")
    snap = durability.snapshot(draft, tmp_path / "backup", reason="manual", repo_root=repo)
    destination = repo / "restore-parent" / "restored.md"
    destination.parent.mkdir()
    original_lstat = Path.lstat

    def marked_lstat(path: Path) -> object:
        observed = original_lstat(path)
        if path.name == "restore-parent":
            values = {
                name: getattr(observed, name)
                for name in dir(observed)
                if name.startswith("st_")
            }
            values["st_file_attributes"] = (
                values.get("st_file_attributes", 0)
                | durability.FILE_ATTRIBUTE_REPARSE_POINT
            )
            return SimpleNamespace(**values)
        return observed

    monkeypatch.setattr(Path, "lstat", marked_lstat)
    with pytest.raises(durability.BoundaryError, match="blob_reparse_point_not_allowed"):
        durability.restore(Path(snap["receipt"]), destination)
    assert not destination.exists()


def test_cli_json_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("x", encoding="utf-8")
    backup = tmp_path / "backup"
    code = durability.main([
        "snapshot", "--draft", str(draft), "--backup-root", str(backup),
        "--repo-root", str(repo), "--reason", "manual", "--json",
    ])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "verified"

    missing = repo / "missing.md"
    code = durability.main([
        "status", "--draft", str(missing), "--backup-root", str(backup),
        "--repo-root", str(repo), "--json",
    ])
    assert code == 2


def test_status_reports_snapshot_from_other_worktree(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    subprocess.run(["git", "init", str(first)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(first), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(first), "config", "user.name", "t"], check=True)
    (first / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(first), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(first), "commit", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(first), "worktree", "add", "-b", "other", str(second)], check=True, capture_output=True)
    source = first / "content" / "drafts" / "article.md"
    source.parent.mkdir(parents=True)
    source.write_text("kept", encoding="utf-8")
    backup = tmp_path / "backup"
    durability.snapshot(source, backup, reason="manual", repo_root=first)

    result = durability.status(
        second / "content" / "drafts" / "article.md", backup, repo_root=second
    )
    assert result["status"] == "found_in_other_worktree"
    assert result["covered"] is False
    assert result["other_worktree_sources"] == [str(source.resolve())]


def test_status_prefers_other_worktree_stop_over_old_local_receipt(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    subprocess.run(["git", "init", str(first)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(first), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(first), "config", "user.name", "t"], check=True)
    (first / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(first), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(first), "commit", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(first), "worktree", "add", "-b", "other", str(second)], check=True, capture_output=True)
    backup = tmp_path / "backup"
    relative = Path("content/drafts/article.md")
    local = second / relative
    local.parent.mkdir(parents=True)
    local.write_text("old", encoding="utf-8")
    durability.snapshot(local, backup, reason="manual", repo_root=second)
    local.unlink()
    active = first / relative
    active.parent.mkdir(parents=True)
    active.write_text("new", encoding="utf-8")
    durability.snapshot(active, backup, reason="manual", repo_root=first)

    result = durability.status(local, backup, repo_root=second)
    assert result["status"] == "found_in_other_worktree"
    assert result["other_worktree_sources"] == [str(active.resolve())]


def test_status_ignores_stale_receipt_from_removed_other_worktree(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    subprocess.run(["git", "init", str(first)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(first), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(first), "config", "user.name", "t"], check=True)
    (first / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(first), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(first), "commit", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(first), "worktree", "add", "-b", "other", str(second)], check=True, capture_output=True)
    source = first / "content" / "drafts" / "article.md"
    source.parent.mkdir(parents=True)
    source.write_text("gone", encoding="utf-8")
    backup = tmp_path / "backup"
    durability.snapshot(source, backup, reason="manual", repo_root=first)
    source.unlink()

    result = durability.status(second / "content" / "drafts" / "article.md", backup, repo_root=second)
    assert result["status"] == "uncovered"
    assert result["covered"] is False


def test_verify_rejects_blob_outside_receipt_namespace(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("safe", encoding="utf-8")
    snap = durability.snapshot(draft, tmp_path / "backup", reason="manual", repo_root=repo)
    receipt = Path(snap["receipt"])
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    outside = tmp_path / "outside.md"
    outside.write_text("other", encoding="utf-8")
    payload["blob"] = str(outside)
    payload["sha256"] = durability._sha256(outside.read_bytes())
    payload["bytes"] = outside.stat().st_size
    receipt.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(durability.BoundaryError, match="receipt_blob_path_mismatch"):
        durability.verify(receipt)


def test_verify_rejects_symlink_blob(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("safe", encoding="utf-8")
    snap = durability.snapshot(draft, tmp_path / "backup", reason="manual", repo_root=repo)
    blob = Path(snap["blob"])
    real_blob = tmp_path / "real-blob.md"
    blob.replace(real_blob)
    try:
        blob.symlink_to(real_blob)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    with pytest.raises(durability.BoundaryError, match="blob_reparse_point_not_allowed"):
        durability.verify(Path(snap["receipt"]))


def test_verify_rejects_symlink_blob_parent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("safe", encoding="utf-8")
    snap = durability.snapshot(draft, tmp_path / "backup", reason="manual", repo_root=repo)
    blob = Path(snap["blob"])
    blobs = blob.parent
    real_blobs = blobs.with_name("real-blobs")
    blobs.replace(real_blobs)
    try:
        blobs.symlink_to(real_blobs, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")

    with pytest.raises(durability.BoundaryError, match="blob_reparse_point_not_allowed"):
        durability.verify(Path(snap["receipt"]))


def test_verify_rejects_mocked_windows_reparse_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("safe", encoding="utf-8")
    snap = durability.snapshot(draft, tmp_path / "backup", reason="manual", repo_root=repo)
    original_lstat = Path.lstat

    def marked_lstat(path: Path) -> object:
        observed = original_lstat(path)
        if path.name == "blobs":
            values = {
                name: getattr(observed, name)
                for name in dir(observed)
                if name.startswith("st_")
            }
            values["st_file_attributes"] = (
                values.get("st_file_attributes", 0)
                | durability.FILE_ATTRIBUTE_REPARSE_POINT
            )
            return SimpleNamespace(**values)
        return observed

    monkeypatch.setattr(Path, "lstat", marked_lstat)
    with pytest.raises(durability.BoundaryError, match="blob_reparse_point_not_allowed"):
        durability.verify(Path(snap["receipt"]))


def test_snapshot_rejects_existing_symlink_blob(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("safe", encoding="utf-8")
    backup = tmp_path / "backup"
    snap = durability.snapshot(draft, backup, reason="manual", repo_root=repo)
    blob = Path(snap["blob"])
    real_blob = tmp_path / "real-snapshot-blob.md"
    blob.replace(real_blob)
    try:
        blob.symlink_to(real_blob)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    with pytest.raises(durability.BoundaryError, match="blob_reparse_point_not_allowed"):
        durability.snapshot(draft, backup, reason="manual", repo_root=repo)


@pytest.mark.parametrize("marked_component", ["blob", "parent"])
def test_snapshot_rejects_mocked_windows_reparse_component(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, marked_component: str
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("safe", encoding="utf-8")
    backup = tmp_path / "backup"
    snap = durability.snapshot(draft, backup, reason="manual", repo_root=repo)
    blob = Path(snap["blob"])
    marked_name = blob.name if marked_component == "blob" else "blobs"
    original_lstat = Path.lstat

    def marked_lstat(path: Path) -> object:
        observed = original_lstat(path)
        if path.name == marked_name:
            values = {
                name: getattr(observed, name)
                for name in dir(observed)
                if name.startswith("st_")
            }
            values["st_file_attributes"] = (
                values.get("st_file_attributes", 0)
                | durability.FILE_ATTRIBUTE_REPARSE_POINT
            )
            return SimpleNamespace(**values)
        return observed

    monkeypatch.setattr(Path, "lstat", marked_lstat)
    with pytest.raises(durability.BoundaryError, match="blob_reparse_point_not_allowed"):
        durability.snapshot(draft, backup, reason="manual", repo_root=repo)


def test_snapshot_rejects_mocked_windows_reparse_receipts_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("safe", encoding="utf-8")
    backup = tmp_path / "backup"
    original_lstat = Path.lstat

    def marked_lstat(path: Path) -> object:
        observed = original_lstat(path)
        if path.name == "receipts":
            values = {
                name: getattr(observed, name)
                for name in dir(observed)
                if name.startswith("st_")
            }
            values["st_file_attributes"] = (
                values.get("st_file_attributes", 0)
                | durability.FILE_ATTRIBUTE_REPARSE_POINT
            )
            return SimpleNamespace(**values)
        return observed

    monkeypatch.setattr(Path, "lstat", marked_lstat)
    with pytest.raises(durability.BoundaryError, match="blob_reparse_point_not_allowed"):
        durability.snapshot(draft, backup, reason="manual", repo_root=repo)


def test_snapshot_rejects_broken_receipt_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("safe", encoding="utf-8")
    backup = tmp_path / "backup"
    digest = durability._sha256(draft.read_bytes())
    blob, generated = durability._paths(draft.resolve(), backup.resolve(), repo.resolve(), digest)
    receipt = generated.parent / "fixed.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    try:
        receipt.symlink_to(tmp_path / "missing-receipt.json")
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    monkeypatch.setattr(durability, "_paths", lambda *args: (blob, receipt))

    with pytest.raises(durability.BoundaryError, match="blob_reparse_point_not_allowed"):
        durability.snapshot(draft, backup, reason="manual", repo_root=repo)


def test_snapshot_receipt_publish_race_does_not_replace_competitor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    draft = repo / "draft.md"
    draft.write_text("safe", encoding="utf-8")
    backup = tmp_path / "backup"
    original_link = durability.os.link
    competitor = b"competitor receipt\n"

    def competing_link(source: str, target: Path) -> None:
        Path(target).write_bytes(competitor)
        original_link(source, target)

    monkeypatch.setattr(durability.os, "link", competing_link)
    with pytest.raises(durability.BoundaryError, match="existing_destination_restore_not_supported"):
        durability.snapshot(draft, backup, reason="manual", repo_root=repo)
    receipts = list(backup.rglob("receipts/*.json"))
    assert len(receipts) == 1
    assert receipts[0].read_bytes() == competitor


@pytest.mark.parametrize("payload", [[], 1, {"schema_version": durability.SCHEMA_VERSION, "blob": []}])
def test_malformed_receipt_is_boundary_error(tmp_path: Path, payload: object) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(durability.BoundaryError, match="receipt_schema_invalid"):
        durability.verify(receipt)


def test_no_platform_backup_location_requires_explicit_root(monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    with pytest.raises(durability.BoundaryError, match="pass --backup-root"):
        durability.default_backup_root()
