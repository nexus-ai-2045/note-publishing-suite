from __future__ import annotations

import json
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/skill_pointer_check.py"


def load_checker_module():
    spec = importlib.util.spec_from_file_location("skill_pointer_check", CHECKER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_checker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), *args, "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_package_pointer_targets_exist() -> None:
    result = run_checker()
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["checked_targets"]


def test_installed_pointer_target_disappearance_fails_closed(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    env = os.environ.copy()
    env["CLAUDE_SKILLS_DIR"] = str(skills_root)
    install = subprocess.run(
        ["bash", "adapters/claude-code/install.sh", str(tmp_path / "workspace")],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr

    pointer = skills_root / "note-publishing-suite" / "SKILL.md"
    pointer.write_text(
        pointer.read_text(encoding="utf-8").replace(
            f"{ROOT}/SKILL.md", f"{ROOT}/missing-ssot/SKILL.md"
        ),
        encoding="utf-8",
    )

    result = run_checker("--installed-root", str(skills_root))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any("missing installed SSOT target" in error for error in payload["errors"])


def install_pointers(skills_root: Path, workspace_root: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CLAUDE_SKILLS_DIR"] = str(skills_root)
    return subprocess.run(
        ["bash", "adapters/claude-code/install.sh", str(workspace_root)],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_installed_pointer_to_existing_wrong_target_fails_closed(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    install = install_pointers(skills_root, tmp_path / "workspace")
    assert install.returncode == 0, install.stdout + install.stderr

    pointer = skills_root / "note-draft-production" / "SKILL.md"
    pointer.write_text(
        pointer.read_text(encoding="utf-8").replace(
            f"{ROOT}/skills/note-draft-production/SKILL.md",
            f"{ROOT}/SKILL.md",
        ),
        encoding="utf-8",
    )

    result = run_checker("--installed-root", str(skills_root))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert any("unexpected installed SSOT target" in error for error in payload["errors"])


def test_installed_pointer_symlink_fails_closed(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    install = install_pointers(skills_root, tmp_path / "workspace")
    assert install.returncode == 0, install.stdout + install.stderr

    pointer = skills_root / "note-draft-production" / "SKILL.md"
    target = tmp_path / "pointer-copy.md"
    target.write_text(pointer.read_text(encoding="utf-8"), encoding="utf-8")
    pointer.unlink()
    pointer.symlink_to(target)

    result = run_checker("--installed-root", str(skills_root))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert any("installed pointer must not be a symlink" in error for error in payload["errors"])


def test_installer_replaces_pointer_symlink_without_overwriting_target(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    pointer_dir = skills_root / "note-draft-production"
    pointer_dir.mkdir(parents=True)
    victim = tmp_path / "victim.md"
    victim.write_text("do not overwrite\n", encoding="utf-8")
    pointer = pointer_dir / "SKILL.md"
    pointer.symlink_to(victim)

    install = install_pointers(skills_root, tmp_path / "workspace")
    assert install.returncode == 0, install.stdout + install.stderr
    assert victim.read_text(encoding="utf-8") == "do not overwrite\n"
    assert pointer.is_symlink() is False
    assert f"{ROOT}/skills/note-draft-production/SKILL.md" in pointer.read_text(
        encoding="utf-8"
    )


def test_package_template_root_escape_fails_closed(tmp_path: Path) -> None:
    checker = load_checker_module()
    package_root = tmp_path / "package"
    adapter_root = package_root / "adapters" / "claude-code"
    template = adapter_root / "note-draft-production" / "SKILL.md"
    template.parent.mkdir(parents=True)
    escaped_target = tmp_path / "evil" / "SKILL.md"
    escaped_target.parent.mkdir(parents=True)
    escaped_target.write_text("evil\n", encoding="utf-8")
    template.write_text(
        "`{{PACKAGE_ROOT}}/../evil/SKILL.md`\n",
        encoding="utf-8",
    )
    checker.ROOT = package_root
    checker.ADAPTER_ROOT = adapter_root

    _, errors = checker.validate_templates()
    assert any("unexpected package SSOT target" in error for error in errors)


def test_installer_rejects_symlinked_adapter_directory(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    redirected_dir = tmp_path / "redirected"
    redirected_dir.mkdir()
    skills_root.mkdir()
    (skills_root / "note-draft-production").symlink_to(
        redirected_dir,
        target_is_directory=True,
    )

    install = install_pointers(skills_root, tmp_path / "workspace")
    assert install.returncode == 1
    assert "installed pointer directory must not be a symlink" in install.stderr
    assert list(redirected_dir.iterdir()) == []


def test_installer_supports_spaces_and_ampersand_in_paths(tmp_path: Path) -> None:
    package_root = tmp_path / "package space & mark"
    shutil.copytree(
        ROOT,
        package_root,
        ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__"),
    )
    skills_root = tmp_path / "skills space & mark"
    env = os.environ.copy()
    env["CLAUDE_SKILLS_DIR"] = str(skills_root)

    install = subprocess.run(
        ["bash", "adapters/claude-code/install.sh", str(tmp_path / "workspace & notes")],
        cwd=package_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert install.returncode == 0, install.stdout + install.stderr
    pointer = skills_root / "note-draft-production" / "SKILL.md"
    assert f"{package_root}/skills/note-draft-production/SKILL.md" in pointer.read_text(
        encoding="utf-8"
    )
