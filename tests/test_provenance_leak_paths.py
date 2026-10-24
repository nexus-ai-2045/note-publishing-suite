from __future__ import annotations

import importlib.util
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "provenance_leak_check.py"
SPEC = importlib.util.spec_from_file_location("nps_provenance_path_regression", SOURCE)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


@pytest.mark.parametrize("separator_count", [1, 2, 4])
@pytest.mark.parametrize("drive", ["C", "D"])
def test_windows_path_is_rejected_with_literal_or_escaped_separators(tmp_path, monkeypatch, separator_count, drive):
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    separator = chr(92) * separator_count
    value = drive + ":" + separator + "Users" + separator + "fixture-operator" + separator + "notes"
    source = tmp_path / "fixture.md"
    source.write_text(value, encoding="utf-8")
    findings = checker.check_files([source], checker.default_rules(), set())
    assert "windows_user_path" in {item["rule_id"] for item in findings}
    assert all(value not in str(item) for item in findings)


def test_posix_path_is_still_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    source = tmp_path / "fixture.md"
    source.write_text(str(PurePosixPath("/", "Users", "fixture-operator", "notes")), encoding="utf-8")
    findings = checker.check_files([source], checker.default_rules(), set())
    assert "posix_user_path" in {item["rule_id"] for item in findings}


def test_relative_public_note_has_no_private_path_finding(tmp_path, monkeypatch):
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    source = tmp_path / "fixture.md"
    source.write_text("content/drafts/public-note.md", encoding="utf-8")
    assert checker.check_files([source], checker.default_rules(), set()) == []


def test_registered_nested_worktree_is_not_parent_package_data(tmp_path, monkeypatch):
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"):
        env.pop(key, None)
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")

    def git(*args):
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=tmp_path,
                       env=env, check=True, capture_output=True)

    git("init", "-q")
    source = tmp_path / "source.md"
    source.write_text("original source remains scanned", encoding="utf-8")
    git("add", "source.md")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "fixture")
    registered = tmp_path / ".worktrees/registered"
    git("worktree", "add", "--detach", str(registered), "HEAD")
    unregistered = tmp_path / ".worktrees/unregistered/source.md"
    unregistered.parent.mkdir(parents=True)
    unregistered.write_text("unregistered files must remain scanned", encoding="utf-8")
    nested = tmp_path / "content/.worktrees/source.md"
    nested.parent.mkdir(parents=True)
    nested.write_text("ordinary source must remain scanned", encoding="utf-8")
    scanned = set(checker.iter_text_files([tmp_path]))
    assert source in scanned and unregistered in scanned and nested in scanned
    assert registered / "source.md" not in scanned
    assert list(checker.iter_text_files([registered / "source.md"])) == [registered / "source.md"]
    assert registered / "source.md" in set(checker.iter_text_files([registered]))


def test_unavailable_worktree_registry_keeps_scanning(tmp_path, monkeypatch):
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    source = tmp_path / ".worktrees/unregistered/source.md"
    source.parent.mkdir(parents=True)
    source.write_text("not managed", encoding="utf-8")
    assert source in set(checker.iter_text_files([tmp_path]))
