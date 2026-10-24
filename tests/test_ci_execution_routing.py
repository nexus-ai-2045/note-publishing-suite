"""実Git差分でUI検査の省略範囲と必須jobの継続を確かめる。"""
from pathlib import Path
import os
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/test.yml"


def _impact_script():
    block = WORKFLOW.read_text(encoding="utf-8").split(
        "      - name: 共同執筆画面への変更を確認\n", 1
    )[1].split("      - name: Node.jsを準備\n", 1)[0]
    return textwrap.dedent(block.split("          python3 - <<'PY'\n", 1)[1].rsplit("          PY", 1)[0])


def _git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


@pytest.fixture
def candidate(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Fixture")
    _git(tmp_path, "config", "user.email", "fixture@example.invalid")
    _git(tmp_path, "config", "core.autocrlf", "false")
    (tmp_path / "README.md").write_bytes(b"base\n")
    ui = tmp_path / "writing-app/source.txt"
    ui.parent.mkdir()
    ui.write_bytes(b"ui\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    return tmp_path, _git(tmp_path, "rev-parse", "HEAD")


def _run(root, base, event="pull_request", ref="refs/pull/1/merge"):
    output = root / "impact-output"
    env = dict(os.environ, CHANGE_BASE=base, CHANGE_EVENT=event,
               CHANGE_REF=ref, GITHUB_OUTPUT=str(output))
    result = subprocess.run([sys.executable, "-c", _impact_script()],
                            cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return output.read_text(encoding="utf-8").strip()


@pytest.mark.parametrize("path,expected", [
    ("docs/article.md", False),
    ("scripts/editor.py", False),
    ("writing-app/package-lock.json", True),
    ("writing-app/src/screen.tsx", True),
    (".github/workflows/test.yml", True),
    (".npmrc", True),
    ("package.json", True),
])
@pytest.mark.parametrize("event,ref", [
    ("pull_request", "refs/pull/1/merge"),
    ("push", "refs/heads/main"),
])
def test_actual_git_changes_select_only_affected_ui(candidate, path, expected, event, ref):
    root, base = candidate
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(b"changed\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "change")
    assert _run(root, base, event, ref) == f"relevant={str(expected).lower()}"


def test_moving_ui_outside_component_still_runs_ui(candidate):
    root, base = candidate
    _git(root, "mv", "writing-app/source.txt", "moved.txt")
    _git(root, "commit", "-qm", "move")
    assert _run(root, base) == "relevant=true"


@pytest.mark.parametrize("base,event,ref", [
    ("", "push", "refs/heads/main"),
    ("0" * 40, "push", "refs/heads/main"),
    ("invalid", "pull_request", "refs/pull/1/merge"),
    (None, "workflow_dispatch", "refs/heads/main"),
    (None, "release", "refs/tags/v1"),
    (None, "push", "refs/tags/v1"),
])
def test_unknown_base_and_explicit_full_checks_do_not_skip(candidate, base, event, ref):
    root, actual = candidate
    assert _run(root, actual if base is None else base, event, ref) == "relevant=true"


def test_required_job_resolves_and_only_ui_work_is_conditional():
    text = WORKFLOW.read_text(encoding="utf-8")
    ui = text.split("  writing-ui:\n", 1)[1].split("  repository-guarantees:\n", 1)[0]
    assert "\n    if:" not in ui
    assert "fetch-depth: 0" in ui
    for step in ("Node.jsを準備", "固定した依存を導入", "原文保持とAPI接続の試験", "型検査と画面build"):
        block = ui.split(f"      - name: {step}\n", 1)[1]
        assert block.startswith("        if: steps.writing-impact.outputs.relevant == 'true'\n")
    assert "  pull_request:" in text and "  push:" in text


def test_verifier_keeps_hosted_checks_without_repeating_same_cli():
    text = WORKFLOW.read_text(encoding="utf-8")
    package = text.split("  package-smoke:\n", 1)[1].split("  windows-installer-smoke:\n", 1)[0]
    verifier = (ROOT / "scripts/verify_public_package.sh").read_text(encoding="utf-8")
    assert package.count("run: sh scripts/verify_public_package.sh") == 1
    for script in ("provenance_leak_check.py", "provenance_label_check.py", "github_identity_guard.py",
                   "japanese_closeout_language_check.py", "note_image_upload_boundary_check.py"):
        assert f"python3 scripts/{script}" in verifier
        assert f"run: python scripts/{script}" not in package
    assert "python -m pytest scripts/test_skill_integration.py tests -q" in package
    assert "needs: repository-guarantees" in package
    assert "scripts\\verify_public_package.ps1" in text


@pytest.mark.parametrize("workflow,event", [
    ("test.yml", "pull_request"), ("preflight.yml", "pull_request"),
    ("base-guard.yml", "pull_request_target"),
])
def test_stale_run_groups_cannot_cancel_another_workflow_or_event(workflow, event):
    text = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
    group = "${{ github.workflow }}-${{ github.event_name }}-${{ github.event.pull_request.number || github.ref }}"
    assert f"  group: {group}-" in text
    assert "&& 'latest' || format('{0}-{1}', github.run_id, github.run_attempt) }}" in text
    assert f"github.event_name == '{event}'" in text
    if workflow != "base-guard.yml":
        assert "github.event_name == 'push' && startsWith(github.ref, 'refs/heads/')" in text
