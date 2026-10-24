from __future__ import annotations

import json
import importlib.util
import os
import shutil

import pytest
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/skill_pointer_check.py"
INSTALL_COMMAND = (
    'mkdir -p "$2" && CLAUDE_SKILLS_DIR="$1" exec bash adapters/claude-code/install.sh "$2"'
)


def require_native_posix_bash() -> None:
    if os.name != "nt":
        return
    probe = subprocess.run(
        ["bash", "-c", "uname -r"],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if "microsoft" in probe.stdout.lower():
        import pytest

        pytest.skip("WSL bash is not the Windows installer; install.ps1 is tested separately")


def load_checker_module():
    spec = importlib.util.spec_from_file_location("skill_pointer_check", CHECKER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def installed_target(pointer: Path) -> str:
    checker = load_checker_module()
    targets = checker.INSTALLED_TARGET_RE.findall(pointer.read_text(encoding="utf-8"))
    assert len(targets) == 1
    return targets[0]


def run_checker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), *args, "--json"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
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


def test_posix_codex_install_replaces_stale_pointer_and_removes_translation(tmp_path: Path) -> None:
    require_native_posix_bash()
    destination = tmp_path / "codex skills & space"
    pointer = destination / "note-postpublish-ledger" / "SKILL.md"
    pointer.parent.mkdir(parents=True)
    pointer.write_text("`/c/missing-package/SKILL.md`\n", encoding="utf-8")
    (tmp_path / "workspace").mkdir()
    env = dict(os.environ, NOTE_SKILL_RUNTIME="codex", CODEX_SKILLS_DIR=str(destination))
    result = subprocess.run(
        ["bash", "adapters/claude-code/install.sh", str(tmp_path / "workspace")],
        cwd=ROOT, env=env, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    body = pointer.read_text(encoding="utf-8")
    assert "Codex pointer" in body
    assert "読み替え" not in body
    assert "/c/missing-package" not in body
    assert "## 作業場所" in body
    assert f"{ROOT}/scripts" in body
    assert "storage.drafts" in body
    assert "storage.ledgers" in body
    assert f"{tmp_path / 'workspace'}/data" not in body
    assert f"{tmp_path / 'workspace'}/scripts" not in body
    assert run_checker("--installed-root", str(destination)).returncode == 0


def test_unknown_posix_runtime_does_not_write(tmp_path: Path) -> None:
    require_native_posix_bash()
    destination = tmp_path / "skills"
    result = subprocess.run(
        ["bash", "adapters/claude-code/install.sh"], cwd=ROOT,
        env=dict(os.environ, NOTE_SKILL_RUNTIME="unknown", CODEX_SKILLS_DIR=str(destination)),
        text=True, capture_output=True,
    )
    assert result.returncode == 1
    assert "unknown NOTE_SKILL_RUNTIME" in result.stderr
    assert not destination.exists()


def test_posix_codex_uses_codex_home(tmp_path: Path) -> None:
    require_native_posix_bash()
    env = dict(os.environ, NOTE_SKILL_RUNTIME="codex", CODEX_HOME=str(tmp_path / "codex"))
    env.pop("CODEX_SKILLS_DIR", None)
    result = subprocess.run(
        ["bash", "adapters/claude-code/install.sh", str(tmp_path)], cwd=ROOT,
        env=env, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "codex/skills/note-postpublish-ledger/SKILL.md").is_file()


def test_codex_missing_or_nonexistent_workspace_does_not_write(tmp_path: Path) -> None:
    require_native_posix_bash()
    destination = tmp_path / "skills"
    for arguments in ([], [str(tmp_path / "missing")]):
        result = subprocess.run(
            ["bash", "adapters/claude-code/install.sh", *arguments], cwd=ROOT,
            env=dict(os.environ, NOTE_SKILL_RUNTIME="codex", CODEX_SKILLS_DIR=str(destination)),
            text=True, capture_output=True,
        )
        assert result.returncode == 1
        assert "explicit existing workspace" in result.stderr
        assert not destination.exists()


def test_installed_target_parser_requires_path_boundary() -> None:
    checker = load_checker_module()
    assert checker.INSTALLED_TARGET_RE.findall("`/tmp/package/SKILL.md`") == [
        "/tmp/package/SKILL.md"
    ]
    assert checker.INSTALLED_TARGET_RE.findall("`/tmp/package/SKILL.md.missing`") == []


def test_installed_pointer_target_disappearance_fails_closed(tmp_path: Path) -> None:
    require_native_posix_bash()
    skills_root = tmp_path / "skills"
    install = subprocess.run(
        [
            "bash",
            "-c",
            INSTALL_COMMAND,
            "bash",
            skills_root.as_posix(),
            (tmp_path / "workspace").as_posix(),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr

    pointer = skills_root / "note-publishing-suite" / "SKILL.md"
    original_target = installed_target(pointer)
    missing_target = str(Path(original_target).parent / "missing" / "SKILL.md")
    pointer.write_text(
        pointer.read_text(encoding="utf-8").replace(
            original_target, missing_target
        ),
        encoding="utf-8",
    )

    result = run_checker("--installed-root", str(skills_root))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any("missing installed SSOT target" in error for error in payload["errors"])


def test_installed_pointer_target_suffix_fails_closed(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    install = install_pointers(skills_root, tmp_path / "workspace")
    assert install.returncode == 0, install.stdout + install.stderr

    pointer = skills_root / "note-publishing-suite" / "SKILL.md"
    original_target = installed_target(pointer)
    pointer.write_text(
        pointer.read_text(encoding="utf-8").replace(
            original_target, f"{original_target}.missing"
        ),
        encoding="utf-8",
    )

    result = run_checker("--installed-root", str(skills_root))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any(
        "installed pointer has no absolute SSOT target" in error
        for error in payload["errors"]
    )


def install_pointers(skills_root: Path, workspace_root: Path) -> subprocess.CompletedProcess[str]:
    require_native_posix_bash()
    return subprocess.run(
        [
            "bash",
            "-c",
            INSTALL_COMMAND,
            "bash",
            skills_root.as_posix(),
            workspace_root.as_posix(),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_installed_pointer_to_existing_wrong_target_fails_closed(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    install = install_pointers(skills_root, tmp_path / "workspace")
    assert install.returncode == 0, install.stdout + install.stderr

    pointer = skills_root / "note-draft-production" / "SKILL.md"
    original_target = installed_target(pointer)
    wrong_target = installed_target(skills_root / "note-publishing-suite" / "SKILL.md")
    pointer.write_text(
        pointer.read_text(encoding="utf-8").replace(
            original_target,
            wrong_target,
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
    try:
        pointer.symlink_to(target)
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            import pytest

            pytest.skip("Windows symlink privilege is unavailable")
        raise

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
    try:
        pointer.symlink_to(victim)
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            import pytest

            pytest.skip("Windows symlink privilege is unavailable")
        raise

    install = install_pointers(skills_root, tmp_path / "workspace")
    assert install.returncode == 0, install.stdout + install.stderr
    assert victim.read_text(encoding="utf-8") == "do not overwrite\n"
    assert pointer.is_symlink() is False
    checker = load_checker_module()
    assert checker.normalized_target(installed_target(pointer)) == (
        ROOT / "skills" / "note-draft-production" / "SKILL.md"
    ).resolve()


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
    try:
        (skills_root / "note-draft-production").symlink_to(
            redirected_dir,
            target_is_directory=True,
        )
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            import pytest

            pytest.skip("Windows symlink privilege is unavailable")
        raise

    install = install_pointers(skills_root, tmp_path / "workspace")
    assert install.returncode == 1
    assert "installed pointer directory must not be a symlink" in install.stderr
    assert list(redirected_dir.iterdir()) == []


def test_installer_supports_spaces_and_ampersand_in_paths(tmp_path: Path) -> None:
    require_native_posix_bash()
    package_root = tmp_path / "package space & mark"
    shutil.copytree(
        ROOT,
        package_root,
        ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__"),
    )
    skills_root = tmp_path / "skills space & mark"
    install = subprocess.run(
        [
            "bash",
            "-c",
            INSTALL_COMMAND,
            "bash",
            skills_root.as_posix(),
            (tmp_path / "workspace & notes").as_posix(),
        ],
        cwd=package_root,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert install.returncode == 0, install.stdout + install.stderr
    pointer = skills_root / "note-draft-production" / "SKILL.md"
    checker = load_checker_module()
    assert checker.normalized_target(installed_target(pointer)) == (
        package_root / "skills" / "note-draft-production" / "SKILL.md"
    ).resolve()


@pytest.mark.parametrize("prefix", ["$HOME", "${HOME}", "~"])
def test_portable_home_pointer_resolves_without_shell(tmp_path, monkeypatch, prefix):
    checker = load_checker_module()
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "package space" / "SKILL.md"
    raw = prefix + "/package space/SKILL.md"
    assert checker.INSTALLED_TARGET_RE.findall("```\n" + raw + "\n```") == [raw]
    assert checker.normalized_target(raw) == target.resolve()


@pytest.mark.parametrize("raw", ["$SECRET/pkg/SKILL.md", "${SECRET}/pkg/SKILL.md", "~other/pkg/SKILL.md", "$HOME/$(touch secret)/SKILL.md", "$HOME/`touch secret`/SKILL.md"])
def test_unsupported_or_executable_portable_paths_are_rejected(raw):
    with pytest.raises(ValueError):
        load_checker_module().normalized_target(raw)


def test_installed_unsupported_env_does_not_fall_back_to_absolute_suffix(tmp_path):
    checker = load_checker_module()
    checker.adapter_names = lambda: ["note-draft-production"]
    p = tmp_path / "note-draft-production/SKILL.md"
    p.parent.mkdir()
    p.write_text("`$SECRET" + str(checker.expected_package_target("note-draft-production")) + "`\n")
    _, errors = checker.validate_installed(tmp_path)
    assert errors


def test_installed_home_target_missing_still_fails_closed(tmp_path, monkeypatch):
    checker = load_checker_module()
    monkeypatch.setenv("HOME", str(tmp_path))
    checker.adapter_names = lambda: ["note-draft-production"]
    p = tmp_path / "note-draft-production/SKILL.md"
    p.parent.mkdir()
    p.write_text("`$HOME/missing/SKILL.md`\n")
    checked, errors = checker.validate_installed(tmp_path)
    assert checked == [str(tmp_path / "missing/SKILL.md")]
    assert any("missing installed SSOT target" in error for error in errors)


@pytest.mark.parametrize("template", ["$(echo {target} )", "$(\necho {target}\n)", "`echo {target} `", "${{OTHER:- {target} }}"])
def test_command_substitution_cannot_extract_canonical_argument_as_target(tmp_path, template):
    checker = load_checker_module()
    checker.adapter_names = lambda: ["note-draft-production"]
    p = tmp_path / "note-draft-production/SKILL.md"
    p.parent.mkdir()
    p.write_text("```\n" + template.format(target=checker.expected_package_target("note-draft-production")) + "\n```\n")
    _, errors = checker.validate_installed(tmp_path)
    assert errors


def test_posix_install_requires_external_workspace_for_both_runtimes(tmp_path: Path) -> None:
    require_native_posix_bash()
    for runtime in ('codex', 'claude'):
        destination = tmp_path / runtime
        for arguments in ([], [str(ROOT)]):
            result = subprocess.run(
                ['bash', 'adapters/claude-code/install.sh', *arguments], cwd=ROOT,
                env=dict(os.environ, NOTE_SKILL_RUNTIME=runtime,
                         CODEX_SKILLS_DIR=str(destination), CLAUDE_SKILLS_DIR=str(destination)),
                text=True, capture_output=True, encoding='utf-8')
            assert result.returncode != 0
            assert not destination.exists()


@pytest.mark.parametrize("prefix", ["${NPS_PACKAGE_ROOT}", "$NPS_PACKAGE_ROOT"])
def test_known_host_root_uses_package_default_without_environment(monkeypatch, prefix):
    checker = load_checker_module()
    monkeypatch.delenv("NPS_PACKAGE_ROOT", raising=False)
    assert checker.normalized_target(prefix + "/SKILL.md") == (checker.ROOT / "SKILL.md").resolve()


@pytest.mark.parametrize("prefix", ["${NPS_PACKAGE_ROOT}", "$NPS_PACKAGE_ROOT"])
@pytest.mark.parametrize("explicit_env", [False, True])
def test_seven_pointers_accept_known_host_root_without_home_package(tmp_path, monkeypatch, prefix, explicit_env):
    checker = load_checker_module()
    host_root = tmp_path / "nondefault package & space"
    host_root.mkdir()
    checker.ROOT = host_root
    home = tmp_path / "home without package"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    if explicit_env:
        monkeypatch.setenv("NPS_PACKAGE_ROOT", str(host_root))
    else:
        monkeypatch.delenv("NPS_PACKAGE_ROOT", raising=False)
    installed = tmp_path / "installed"
    names = checker.adapter_names()
    assert len(names) == 7
    for name in names:
        target = checker.expected_package_target(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("本文\n")
        pointer = installed / name / "SKILL.md"
        pointer.parent.mkdir(parents=True)
        suffix = "/SKILL.md" if name == "note-publishing-suite" else f"/skills/{name}/SKILL.md"
        pointer.write_text("`" + prefix + suffix + "`\n")
    checked, errors = checker.validate_installed(installed)
    assert errors == []
    assert len(checked) == 7
    assert all(Path(value).is_relative_to(host_root) for value in checked)


@pytest.mark.parametrize("value", ["", " ", "relative/package", "~/package", "$HOME/package", "${OTHER}/package", "/tmp/`id`", "/tmp/$(id)", "/tmp/package\nother"])
def test_explicit_invalid_host_root_fails_closed(monkeypatch, value):
    checker = load_checker_module()
    monkeypatch.setenv("NPS_PACKAGE_ROOT", value)
    with pytest.raises(ValueError):
        checker.normalized_target("${NPS_PACKAGE_ROOT}/SKILL.md")


def test_host_root_cannot_redirect_checker_to_another_existing_package(tmp_path, monkeypatch):
    checker = load_checker_module()
    checker.adapter_names = lambda: ["note-publishing-suite"]
    other = tmp_path / "other-package"
    other.mkdir()
    (other / "SKILL.md").write_text("別checkout\n")
    monkeypatch.setenv("NPS_PACKAGE_ROOT", str(other))
    installed = tmp_path / "installed"
    pointer = installed / "note-publishing-suite/SKILL.md"
    pointer.parent.mkdir(parents=True)
    pointer.write_text("`${NPS_PACKAGE_ROOT}/SKILL.md`\n")
    _, errors = checker.validate_installed(installed)
    assert any("unexpected installed SSOT target" in error for error in errors)


@pytest.mark.parametrize("expression", ["${NPS_PACKAGE_ROOT:-/tmp}/SKILL.md", "$NPS_PACKAGE_ROOT_SUFFIX/SKILL.md", "$(echo ${NPS_PACKAGE_ROOT}/SKILL.md)", "${NPS_PACKAGE_ROOT}/$(echo SKILL.md)"])
def test_host_root_expressions_cannot_fall_back_to_canonical_suffix(tmp_path, monkeypatch, expression):
    checker = load_checker_module()
    checker.adapter_names = lambda: ["note-publishing-suite"]
    monkeypatch.setenv("NPS_PACKAGE_ROOT", str(checker.ROOT))
    pointer = tmp_path / "note-publishing-suite/SKILL.md"
    pointer.parent.mkdir()
    pointer.write_text("```\n" + expression + "\n```\n")
    _, errors = checker.validate_installed(tmp_path)
    assert errors


@pytest.fixture
def linked_package(tmp_path, monkeypatch):
    """空のGit repositoryとlinked worktreeを作り、commitは作らない。"""
    primary = tmp_path / "primary"
    linked = tmp_path / "linked"
    subprocess.run(["git", "init", str(primary)], check=True, capture_output=True)
    result = subprocess.run(
        ["git", "-C", str(primary), "worktree", "add", "--orphan", "-b", "linked", str(linked)],
        text=True, capture_output=True,
    )
    if result.returncode and "unknown option" in result.stderr:
        pytest.skip("Git worktree --orphan is unavailable: " + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    for package in (primary, linked):
        (package / "SKILL.md").write_text("本文\n", encoding="utf-8")
    checker = load_checker_module()
    monkeypatch.setattr(checker, "ROOT", linked)
    monkeypatch.setattr(checker, "adapter_names", lambda: ["note-publishing-suite"])
    monkeypatch.delenv("NPS_PACKAGE_ROOT", raising=False)
    installed = tmp_path / "installed"
    pointer = installed / "note-publishing-suite/SKILL.md"
    pointer.parent.mkdir(parents=True)
    return checker, primary, linked, installed, pointer


def test_linked_worktree_accepts_primary_installed_pointer(linked_package):
    checker, primary, linked, installed, pointer = linked_package
    pointer.write_text(f"`{primary}/SKILL.md`\n", encoding="utf-8")
    checked, errors = checker.validate_installed(installed)
    assert errors == []
    assert checked == [str(primary / "SKILL.md")]
    assert checker.expected_package_target("note-publishing-suite") == linked / "SKILL.md"


@pytest.mark.parametrize("target_kind", ["other_repository", "arbitrary", "expression"])
def test_linked_worktree_rejects_unrelated_installed_pointer(linked_package, tmp_path, target_kind):
    checker, primary, _, installed, pointer = linked_package
    other = tmp_path / "other"
    other.mkdir()
    (other / "SKILL.md").write_text("別package\n", encoding="utf-8")
    if target_kind == "other_repository":
        subprocess.run(["git", "init", str(other)], check=True, capture_output=True)
    target = f"{other}/SKILL.md"
    if target_kind == "expression":
        target = f"$(echo {primary}/SKILL.md)"
    pointer.write_text(f"```\n{target}\n```\n", encoding="utf-8")
    _, errors = checker.validate_installed(installed)
    assert errors


def test_linked_worktree_requires_primary_skill_file(linked_package):
    checker, primary, _, installed, pointer = linked_package
    (primary / "SKILL.md").unlink()
    pointer.write_text(f"`{primary}/SKILL.md`\n", encoding="utf-8")
    _, errors = checker.validate_installed(installed)
    assert errors


def test_linked_worktree_preserves_current_checkout_pointer(linked_package):
    checker, _, linked, installed, pointer = linked_package
    pointer.write_text(f"`{linked}/SKILL.md`\n", encoding="utf-8")
    _, errors = checker.validate_installed(installed)
    assert errors == []


def test_linked_worktree_rejects_mixed_package_roots(linked_package, monkeypatch):
    checker, primary, linked, installed, pointer = linked_package
    monkeypatch.setattr(checker, "adapter_names", lambda: ["note-publishing-suite", "note-draft-production"])
    target = linked / "skills/note-draft-production/SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("本文\n", encoding="utf-8")
    pointer.write_text(f"`{primary}/SKILL.md`\n", encoding="utf-8")
    second = installed / "note-draft-production/SKILL.md"
    second.parent.mkdir()
    second.write_text(f"`{target}`\n", encoding="utf-8")
    _, errors = checker.validate_installed(installed)
    assert any("mixed installed package roots" in error for error in errors)


def test_linked_worktree_rejects_installed_pointer_symlink(linked_package, tmp_path):
    checker, primary, _, installed, pointer = linked_package
    copy = tmp_path / "pointer.md"
    copy.write_text(f"`{primary}/SKILL.md`\n", encoding="utf-8")
    try:
        pointer.symlink_to(copy)
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege is unavailable")
        raise
    _, errors = checker.validate_installed(installed)
    assert any("installed pointer must not be a symlink" in error for error in errors)


def test_linked_worktree_reports_selected_installed_root(linked_package, monkeypatch):
    checker, primary, linked, installed, pointer = linked_package
    monkeypatch.setattr(checker, "validate_templates", lambda: ([], []))
    for kind, root in (("primary_canonical", primary), ("current_checkout", linked)):
        pointer.write_text(f"`{root}/SKILL.md`\n", encoding="utf-8")
        result = checker.build_result(installed)
        assert result["ok"] is True
        assert result["installed_target_kind"] == kind


def test_linked_worktree_rejects_another_linked_worktree(linked_package, tmp_path):
    checker, primary, _, installed, pointer = linked_package
    sibling = tmp_path / "sibling"
    subprocess.run(
        ["git", "-C", str(primary), "worktree", "add", "--orphan", "-b", "sibling", str(sibling)],
        check=True, capture_output=True,
    )
    (sibling / "SKILL.md").write_text("別worktree\n", encoding="utf-8")
    pointer.write_text(f"`{sibling}/SKILL.md`\n", encoding="utf-8")
    _, errors = checker.validate_installed(installed)
    assert any("unexpected installed SSOT target" in error for error in errors)


@pytest.mark.parametrize("injection", ["common_dir", "git_dir", "work_tree", "config_count", "config_parameters", "config_file"])
def test_linked_worktree_ignores_repository_environment(linked_package, tmp_path, monkeypatch, injection):
    checker, primary, linked, installed, pointer = linked_package
    other = tmp_path / "impostor"
    subprocess.run(["git", "init", str(other)], check=True, capture_output=True)
    (other / "SKILL.md").write_text("別clone\n", encoding="utf-8")
    variables = {
        "common_dir": {"GIT_COMMON_DIR": str(other / ".git")},
        "git_dir": {"GIT_DIR": str(other / ".git")},
        "work_tree": {"GIT_WORK_TREE": str(other)},
        "config_count": {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.worktree", "GIT_CONFIG_VALUE_0": str(other)},
        "config_parameters": {"GIT_CONFIG_PARAMETERS": "'core.worktree=" + str(other) + "'"},
        "config_file": {"GIT_CONFIG_GLOBAL": str(tmp_path / "injected.gitconfig")},
    }[injection]
    (tmp_path / "injected.gitconfig").write_text(f"[core]\n\tworktree = {other}\n", encoding="utf-8")
    for key, value in variables.items():
        monkeypatch.setenv(key, value)
    environment = dict(os.environ)
    pointer.write_text(f"`{other}/SKILL.md`\n", encoding="utf-8")
    _, errors = checker.validate_installed(installed)
    assert any("unexpected installed SSOT target" in error for error in errors)
    pointer.write_text(f"`{primary}/SKILL.md`\n", encoding="utf-8")
    _, errors = checker.validate_installed(installed)
    assert errors == []
    assert dict(os.environ) == environment
