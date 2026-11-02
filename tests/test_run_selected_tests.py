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


@pytest.fixture
def version_repo(tmp_path):
    import json

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".pytest_cache/\n")
    (tmp_path / "package.yaml").write_text("name: fixture\nversion: 1.2.3\ncontract: preserved\n")
    policy = {"rules": [{"changes": ["package.yaml", "adapters/**"],
                          "tests": ["tests/test_package_contract.py"],
                          "checks": []}]}
    (tmp_path / ".test-selection.json").write_text(json.dumps(policy))
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Fixture", "-c",
                    "user.email=fixture@example.invalid", "commit", "-qm", "base"], check=True)
    return tmp_path


def test_version_only_private_policy_preserves_owner_contract_and_hashes(version_repo):
    import hashlib
    import json

    module = adapter()
    package = version_repo / "package.yaml"
    package.write_text(package.read_text().replace("1.2.3", "1.2.4"))
    original = (version_repo / ".test-selection.json").read_bytes()
    with module.selection_policy(version_repo, "HEAD") as (path, binding):
        assert path != version_repo / ".test-selection.json"
        effective = json.loads(path.read_text())
        assert binding["package_version_only"] is True
        assert binding["original_policy_sha256"] == hashlib.sha256(original).hexdigest()
        assert binding["effective_policy_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert binding["base_package_sha256"] != binding["current_package_sha256"]
        assert binding["current_version"] == [1, 2, 4]
        assert effective["rules"][0]["changes"] == ["adapters/**"]
        assert effective["rules"][-1]["dependency_mode"] == "mapped"
        assert set(effective["rules"][-1]["tests"]) == {
            "tests/test_package_contract.py", "tests/test_docs_sync_check.py"}
    assert not path.exists()
    assert (version_repo / ".test-selection.json").read_bytes() == original


@pytest.mark.parametrize("current", [
    "name: fixture\nversion: 1.2.4\ncontract: altered\n",
    "name: fixture\nversion: 1.2.4\nversion: 1.2.5\ncontract: preserved\n",
    "name: fixture\nversion: invalid\ncontract: preserved\n",
    "name: fixture\nversion: 1.2.4\ncontract: preserved \n",
])
def test_non_version_bytes_or_invalid_metadata_keep_original_auto_policy(version_repo, current):
    (version_repo / "package.yaml").write_text(current)
    with adapter().selection_policy(version_repo, "HEAD") as (path, binding):
        assert path == version_repo / ".test-selection.json"
        assert binding["package_version_only"] is False
        assert binding["original_policy_sha256"] == binding["effective_policy_sha256"]


def test_duplicate_base_version_keeps_original_auto_policy(version_repo):
    package = version_repo / "package.yaml"
    package.write_text(package.read_text() + "version: 1.2.3\n")
    subprocess.run(["git", "-C", str(version_repo), "add", "package.yaml"], check=True)
    subprocess.run(["git", "-C", str(version_repo), "-c", "user.name=Fixture", "-c",
                    "user.email=fixture@example.invalid", "commit", "-qm", "duplicate"], check=True)
    package.write_text("name: fixture\nversion: 1.2.4\ncontract: preserved\n")
    assert adapter().package_version_only(version_repo, "HEAD") is None


def test_symlink_package_keeps_original_auto_policy(version_repo, tmp_path):
    package = version_repo / "package.yaml"
    target = tmp_path / "other.yaml"
    target.write_text(package.read_text().replace("1.2.3", "1.2.4"))
    package.unlink()
    try:
        package.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    assert adapter().package_version_only(version_repo, "HEAD") is None


@pytest.mark.parametrize("field,value", [
    ("tests", "tests/test_package_contract.py"), ("checks", "package-check"),
    ("dependency_mode", "unsupported"), ("no_tests", "true"),
])
def test_invalid_owner_rule_is_not_repaired_by_metadata_mapping(version_repo, field, value):
    import json

    package = version_repo / "package.yaml"
    package.write_text(package.read_text().replace("1.2.3", "1.2.4"))
    path = version_repo / ".test-selection.json"
    policy = json.loads(path.read_text())
    policy["rules"][0][field] = value
    path.write_text(json.dumps(policy))
    with pytest.raises(ValueError, match="selection policy"):
        with adapter().selection_policy(version_repo, "HEAD"):
            pytest.fail("invalid owner policy became effective")


def test_package_replacement_after_plan_stops_before_pytest(version_repo):
    import json

    package = version_repo / "package.yaml"
    package.write_text(package.read_text().replace("1.2.3", "1.2.4"))
    (version_repo / "tests").mkdir()
    (version_repo / "tests/test_forbidden.py").write_text(
        "from pathlib import Path\ndef test_forbidden(): Path('executed-marker').write_text('bad')\n")
    selector = version_repo / "selector.py"
    selector.write_text(
        "from pathlib import Path\nimport json\n"
        "p=Path('package.yaml'); p.write_text(p.read_text().replace('1.2.4','1.2.5'))\n"
        "print(" + repr(json.dumps(plan(["tests/test_forbidden.py"]))) + ")\n")
    receipt = version_repo / "receipt.json"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/run_selected_tests.py"),
                             "--repo", str(version_repo), "--selector-script", str(selector),
                             "--base-ref", "HEAD", "--receipt", str(receipt)],
                            capture_output=True, text=True)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "version metadata inputs changed" in result.stderr
    assert not (version_repo / "executed-marker").exists()
    recorded = json.loads(receipt.read_text())
    assert recorded["executed"] is False
    assert recorded["status"] == "unresolved"
    assert recorded["binding"]["package_version_only"] is True
