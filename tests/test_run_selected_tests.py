"""選択入口の空plan・未解決・argv契約を合成repoで確かめる。"""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def adapter():
    spec = importlib.util.spec_from_file_location("selected_runner", ROOT / "scripts/run_selected_tests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan(tests=(), **extra):
    return {"schema": "test-selection/v1", "status": "selected" if tests else "no_tests",
            "selected_tests": list(tests), "checks": [], "unresolved": [], **extra}


def test_empty_plan_never_starts_pytest(tmp_path):
    assert adapter().test_command(tmp_path, plan(), "python") is None


def test_receipts_redact_paths_without_changing_execution_argv(tmp_path):
    import json

    repo = tmp_path / "private-workspace"
    selector = tmp_path / "private-tools" / "selector.py"
    command = [sys.executable, str(selector), "--repo", str(repo)]
    value = {"binding": {"repo": str(repo), "head": "a" * 40}, "command": command}
    displayed = adapter().receipt_text(value, repo, selector)
    assert str(repo) not in displayed and str(selector) not in displayed
    assert sys.executable not in displayed
    assert json.loads(displayed)["command"] == ["<python>", "<selector>", "--repo", "<repo>"]
    assert command == [sys.executable, str(selector), "--repo", str(repo)]
    assert json.loads(displayed)["binding"]["head"] == "a" * 40


@pytest.mark.parametrize("extra", [
    {"status": "unresolved", "unresolved": [{"file": "unknown"}]},
    {"checks": ["not-dispatched"]},
    {"status": "unexpected"},
])
def test_unresolved_or_required_check_is_not_python_success(tmp_path, extra):
    with pytest.raises(ValueError):
        adapter().test_command(tmp_path, plan(**extra), "python")


def test_paths_are_argv_without_shell_interpretation(tmp_path):
    target = "tests/test_space & literal.py"
    (tmp_path / "tests").mkdir()
    (tmp_path / target).write_text("def test_ok(): pass\n")
    command = adapter().test_command(tmp_path, plan([target]), "python")
    assert command == [sys.executable, "-m", "pytest", "-q", "--", target]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("target", ["../test_escape.py", "/test_absolute.py", "-q", "tests"])
def test_invalid_test_paths_rejected(tmp_path, target):
    with pytest.raises(ValueError):
        adapter().test_command(tmp_path, plan([target]), "python")


def test_environment_uses_same_plan_and_keeps_native_test_on_windows(tmp_path):
    paths = ["tests/test_windows_skill_installer.py", "tests/test_owned.py"]
    (tmp_path / "tests").mkdir()
    for path in paths:
        (tmp_path / path).write_text("def test_ok(): pass\n")
    selected = plan(paths)
    assert adapter().test_command(tmp_path, selected, "python")[-1:] == [paths[1]]
    assert adapter().test_command(tmp_path, selected, "windows")[-1:] == [paths[0]]


def test_cli_empty_and_checks_only_do_not_launch_pytest(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Fixture", "-c",
                    "user.email=fixture@example.invalid", "commit", "--allow-empty", "-qm", "base"], check=True)
    (tmp_path / ".test-selection.json").write_text("{}")
    selector = tmp_path / "selector.py"
    receipt = tmp_path / "receipt.json"
    import json
    for extra, expected in [({}, 0), ({"checks": ["needs-real-check"]}, 2),
                            ({"status": "unresolved", "unresolved": [{"file": "unknown"}]}, 2)]:
        selector.write_text("import json\nprint(" + repr(json.dumps(plan(**extra))) + ")\n")
        result = subprocess.run([sys.executable, str(ROOT / "scripts/run_selected_tests.py"),
                                 "--repo", str(tmp_path), "--selector-script", str(selector),
                                 "--base-ref", "HEAD", "--receipt", str(receipt)],
                                capture_output=True, text=True)
        assert result.returncode == expected, result.stdout + result.stderr
        assert "test session starts" not in result.stdout
        if not expected:
            recorded = json.loads(receipt.read_text())
            assert recorded["executed"] is False
            assert recorded["pytest_command"] is None
            assert len(recorded["binding"]["policy_file_sha256"]) == 64
