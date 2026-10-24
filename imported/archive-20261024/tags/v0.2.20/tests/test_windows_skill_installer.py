from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    os.name != "nt",
    reason="install.ps1 and junction behavior require native Windows",
)


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "adapters" / "codex" / "install.ps1"
CHECKER = ROOT / "scripts" / "skill_pointer_check.py"


def copy_package(tmp_path: Path) -> Path:
    package = tmp_path / "package"
    shutil.copytree(
        ROOT,
        package,
        ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__"),
    )
    return package


def make_junction(link: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def run_installer(destination: Path, workspace: Path, package: Path = ROOT):
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALLER),
            "-PackageRoot",
            str(package),
            "-WorkspaceRoot",
            str(workspace),
            "-DestinationRoot",
            str(destination),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_codex_installer_supports_windows_absolute_paths_spaces_and_ampersand(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "Codex skills & local"
    workspace = tmp_path / "Note workspace & drafts"

    result = run_installer(destination, workspace)

    assert result.returncode == 0, result.stdout + result.stderr
    pointer = destination / "note-publishing-suite" / "SKILL.md"
    assert pointer.is_file()
    assert not pointer.is_symlink()
    text = pointer.read_text(encoding="utf-8-sig")
    assert f"{ROOT}/SKILL.md" in text
    assert f"{workspace}/content/drafts" in text
    assert "Claude Code" not in text

    check = subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--installed-root",
            str(destination),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert check.returncode == 0, check.stdout + check.stderr
    assert json.loads(check.stdout)["ok"] is True


def test_codex_installer_atomically_replaces_regular_pointer(tmp_path: Path) -> None:
    destination = tmp_path / "skills"
    pointer = destination / "note-publishing-suite" / "SKILL.md"
    pointer.parent.mkdir(parents=True)
    pointer.write_text("stale pointer\n", encoding="utf-8")

    result = run_installer(destination, tmp_path / "workspace")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "stale pointer" not in pointer.read_text(encoding="utf-8-sig")
    assert not list(pointer.parent.glob(".SKILL.md.*.tmp"))


def test_codex_installer_fails_closed_for_missing_package_root(tmp_path: Path) -> None:
    destination = tmp_path / "skills"

    result = run_installer(
        destination,
        tmp_path / "workspace",
        tmp_path / "missing package",
    )

    assert result.returncode != 0
    assert not destination.exists()


def test_codex_installer_preflights_every_template_before_destination_change(
    tmp_path: Path,
) -> None:
    package = copy_package(tmp_path)
    missing_template = (
        package
        / "adapters"
        / "claude-code"
        / "note-publishing-suite"
        / "SKILL.md"
    )
    missing_template.unlink()
    destination = tmp_path / "skills"
    existing = destination / "note-publishing-suite" / "SKILL.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("original\n", encoding="utf-8")

    result = run_installer(destination, tmp_path / "workspace", package)

    assert result.returncode != 0
    assert existing.read_text(encoding="utf-8") == "original\n"
    assert sorted(path.name for path in destination.iterdir()) == [
        "note-publishing-suite"
    ]


def test_codex_installer_rolls_back_when_final_validation_fails(tmp_path: Path) -> None:
    package = copy_package(tmp_path)
    checker = package / "scripts" / "skill_pointer_check.py"
    checker.write_text("raise SystemExit(17)\n", encoding="utf-8")
    destination = tmp_path / "skills"
    existing = destination / "note-publishing-suite" / "SKILL.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("original\n", encoding="utf-8")

    result = run_installer(destination, tmp_path / "workspace", package)

    assert result.returncode != 0
    assert existing.read_text(encoding="utf-8") == "original\n"
    assert sorted(path.name for path in destination.iterdir()) == [
        "note-publishing-suite"
    ]


def test_codex_installer_rolls_back_prior_pointer_when_commit_fails_midway(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "skills"
    first_pointer = destination / "note-draft-production" / "SKILL.md"
    first_pointer.parent.mkdir(parents=True)
    first_pointer.write_text("original first\n", encoding="utf-8")
    blocker = destination / "note-editor-prepublish"
    blocker.write_text("not a directory\n", encoding="utf-8")

    result = run_installer(destination, tmp_path / "workspace")

    assert result.returncode != 0
    assert first_pointer.read_text(encoding="utf-8") == "original first\n"
    assert blocker.read_text(encoding="utf-8") == "not a directory\n"
    assert not list(first_pointer.parent.glob(".SKILL.md.*"))


def test_codex_installer_removes_temp_when_pointer_move_fails(tmp_path: Path) -> None:
    destination = tmp_path / "skills"
    pointer_directory = destination / "note-draft-production" / "SKILL.md"
    pointer_directory.mkdir(parents=True)

    result = run_installer(destination, tmp_path / "workspace")

    assert result.returncode != 0
    assert pointer_directory.is_dir()
    assert not list(pointer_directory.parent.glob(".SKILL.md.*.tmp"))


def test_codex_installer_rejects_destination_that_is_a_junction(tmp_path: Path) -> None:
    physical = tmp_path / "physical"
    destination = tmp_path / "skills"
    make_junction(destination, physical)

    result = run_installer(destination, tmp_path / "workspace")

    assert result.returncode != 0
    assert list(physical.iterdir()) == []


def test_codex_installer_rejects_nonexistent_destination_below_junction(
    tmp_path: Path,
) -> None:
    physical = tmp_path / "physical"
    junction = tmp_path / "redirected"
    make_junction(junction, physical)
    destination = junction / "nested" / "skills"

    result = run_installer(destination, tmp_path / "workspace")

    assert result.returncode != 0
    assert not (physical / "nested").exists()


def test_codex_installer_rejects_package_root_below_junction(tmp_path: Path) -> None:
    physical_parent = tmp_path / "physical packages"
    junction = tmp_path / "packages"
    make_junction(junction, physical_parent)
    package = copy_package(physical_parent)
    package_through_junction = junction / package.name
    destination = tmp_path / "skills"

    result = run_installer(
        destination,
        tmp_path / "workspace",
        package_through_junction,
    )

    assert result.returncode != 0
    assert not destination.exists()
