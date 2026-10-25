"""Secret-bearing CI invokes pinned tooling, never candidate Python/package code."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/repository-guarantees.yml"


def _secret_script():
    text = WORKFLOW.read_text(encoding="utf-8")
    block = text.split("      - name: repo-preflight readiness_scan (evidence)", 1)[1]
    block = block.split("  repository-guarantees:", 1)[0]
    source = block.split("          python -I - <<'PY'\n", 1)[1].rsplit("          PY", 1)[0]
    return "\n".join(line[10:] for line in source.splitlines())


def _git(root, *args):
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        env.pop(key, None)
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return subprocess.check_output(
        ["git", "-c", "core.hooksPath=/dev/null", *args], cwd=root,
        env=env, text=True, stderr=subprocess.DEVNULL,
    ).strip()


def _repo(root):
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
         "commit", "--allow-empty", "-qm", "fixture")
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def readiness(tmp_path):
    target = tmp_path / "target"
    head = _repo(target)
    runner = tmp_path / "runner"
    runner.mkdir()
    trusted = runner / "repo-preflight"
    pin = _repo(trusted)
    scripts = trusted / "scripts"
    scripts.mkdir()
    (scripts / "identity_gate.py").write_text('''
import json, os, pathlib
from types import SimpleNamespace
def load_policy():
    policy = json.loads(pathlib.Path(os.environ["PREFLIGHT_PRIVATE_PATTERNS_FILE"]).read_text())
    assert policy == {"valid": True}
def load_public_policy():
    return SimpleNamespace(committer_only={"Platform <platform@example.invalid>"})
''', encoding="utf-8")
    (scripts / "readiness_scan.py").write_text('''
import json, os, pathlib, stat, subprocess, sys
assert "PRIVATE_DENYLIST_INPUT" not in os.environ
assert "PRIVATE_PATTERNS_INPUT" not in os.environ
assert pathlib.Path.cwd() == pathlib.Path(os.environ["RUNNER_TEMP"])
assert "--repo" in sys.argv and "--intent" in sys.argv and "--base-ref" in sys.argv
# A tiny trusted-scanner fixture: the author policy permits Fixture, not the
# platform-generated merge identity. Production uses the pinned full validator.
assert subprocess.check_output(["git", "show", "-s", "--format=%cn", "HEAD"],
    cwd=os.environ["GITHUB_WORKSPACE"], text=True).strip() == "Fixture"
for key in ("PUBLIC_IDENTITY_DENYLIST", "PREFLIGHT_PRIVATE_PATTERNS_FILE"):
    path = pathlib.Path(os.environ[key])
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not path.is_relative_to(pathlib.Path(os.environ["GITHUB_WORKSPACE"]))
policy = json.loads(pathlib.Path(os.environ["PREFLIGHT_PRIVATE_PATTERNS_FILE"]).read_text())
pathlib.Path(os.environ["RUNNER_TEMP"], "scanner-called").touch()
assert policy == {"valid": True, "allow_emails": ["platform@example.invalid"]}
assert "--require-private-identity" in sys.argv
assert sys.argv[sys.argv.index("--allowed-identities") + 1] == str(pathlib.Path(os.environ["RUNNER_TEMP"], "repo-preflight/references/public-commit-identities.json"))
print(json.dumps({"scan": {"status": "pass", "head": os.environ["TARGET_HEAD_SHA"],
    "checks": {"private_identity_scan": {"status": "pass"}, "identity_gate": {"status": "pass"}, "public_attribution": {"status": "pass"}}}}))
''', encoding="utf-8")
    # A candidate Python startup hook must never execute in the secret process.
    marker = tmp_path / "candidate-executed"
    (target / "sitecustomize.py").write_text(
        f"from pathlib import Path; Path({str(marker)!r}).touch()", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        RUNNER_TEMP=str(runner), GITHUB_WORKSPACE=str(target), TARGET_HEAD_SHA=head,
        REPO_PREFLIGHT_SHA=pin, GITHUB_EVENT_NAME="pull_request", PIPELINE_CALL="true",
        CONSISTENCY_REMOTE_REF="refs/remotes/origin/nps-ci-base", INITIAL_ROOT="",
        PRIVATE_DENYLIST_INPUT="private-canary-denylist",
        PRIVATE_PATTERNS_INPUT=json.dumps({"valid": True}), PYTHONPATH=str(target),
    )
    return env, runner, marker


def _run(env, runner):
    result = subprocess.run(
        [sys.executable, "-I", "-"], input=_secret_script(), cwd=runner,
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert not list(runner.glob("nps-private-*")), "private files must be removed"
    return result


def test_private_readiness_isolated_success(readiness):
    env, runner, marker = readiness
    result = _run(env, runner)
    assert result.returncode == 0 and result.stdout == "private readiness: pass\n"
    assert result.stderr == "" and not marker.exists()
    assert (runner / "scanner-called").exists()


@pytest.mark.parametrize("key,value", [
    ("PRIVATE_DENYLIST_INPUT", ""), ("PRIVATE_PATTERNS_INPUT", " "),
    ("TARGET_HEAD_SHA", "0" * 40), ("REPO_PREFLIGHT_SHA", "0" * 40),
])
def test_missing_inputs_or_unbound_code_fail_before_scanner(readiness, key, value):
    env, runner, marker = readiness
    env[key] = value
    result = _run(env, runner)
    assert result.returncode == 1 and result.stdout.endswith("private readiness: failed\n")
    assert result.stderr == "" and not marker.exists()
    assert not (runner / "scanner-called").exists()


def test_invalid_private_policy_fails_without_logging_input(readiness):
    env, runner, _ = readiness
    env["PRIVATE_PATTERNS_INPUT"] = "private-canary-invalid-json"
    result = _run(env, runner)
    assert result.returncode == 1
    assert "private-canary" not in result.stdout + result.stderr
    assert result.stderr == ""


def test_scanner_output_is_not_forwarded_to_public_log(readiness):
    env, runner, _ = readiness
    scanner = runner / "repo-preflight/scripts/readiness_scan.py"
    scanner.write_text(
        "import sys; print('private-canary-stdout'); "
        "print('private-canary-stderr',file=sys.stderr); raise SystemExit(1)", encoding="utf-8")
    result = _run(env, runner)
    assert result.returncode == 1 and result.stdout.endswith("private readiness: failed\n")
    assert result.stderr == "" and "private-canary" not in result.stdout


@pytest.mark.parametrize("checks", [
    {"private_identity_scan": {"status": "pass"}, "identity_gate": {"status": "pass"}},
    {"private_identity_scan": {"status": "pass"}, "identity_gate": {"status": "pass"}, "public_attribution": {"status": "fail"}},
    {}, {"private_identity_scan": {"status": "not_configured"}, "identity_gate": {"status": "pass"}},
    {"private_identity_scan": {"status": "pass"}, "identity_gate": {"status": "fail"}},
])
def test_overall_pass_does_not_replace_private_check_results(readiness, checks):
    env, runner, _ = readiness
    payload = {"scan": {"status": "pass", "head": env["TARGET_HEAD_SHA"], "checks": checks}}
    scanner = runner / "repo-preflight/scripts/readiness_scan.py"
    scanner.write_text(f"print({json.dumps(payload)!r})", encoding="utf-8")
    result = _run(env, runner)
    assert result.returncode == 1 and result.stdout.endswith("private readiness: failed\n")
    assert result.stderr == ""


def test_secret_job_never_installs_or_runs_candidate_code():
    text = WORKFLOW.read_text(encoding="utf-8")
    private, candidate = text.split("  repository-guarantees:\n", 1)
    assert "needs: private-readiness" in candidate
    assert "secrets." not in candidate
    assert "pip install" not in private and "ai_ratchet_gate" not in private
    assert "python scripts/" not in private and "npm " not in private
    assert "capture_output=True" in _secret_script()
    assert 'sys.path.insert(0,p)' in _secret_script()
    assert '"-I", "-c"' in _secret_script()
    assert "upload-artifact" not in text
    caller = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    binding = caller.split("  repository-guarantees:", 1)[1].split("  package-smoke:", 1)[0]
    for name in ("NPS_PRIVATE_IDENTITY_DENYLIST", "NPS_PRIVATE_IDENTITY_PATTERNS"):
        assert f"      {name}:\n        required: true" in private
        assert f"      {name}: ${{{{ secrets.{name} }}}}" in binding
    assert "secrets: inherit" not in binding


def test_authored_identity_and_generated_integration_commit_are_separately_bound():
    text = WORKFLOW.read_text(encoding="utf-8")
    private, candidate = text.split("  repository-guarantees:\n", 1)
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in private
    assert "TARGET_HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" in private
    assert "ref: ${{ github.sha }}" in candidate
    assert "INTEGRATION_HEAD: ${{ github.sha }}" in candidate
    assert "CHECKED_BASE: ${{ needs.private-readiness.outputs.event_base }}" in candidate
    assert "CONSISTENCY_BASE: ${{ needs.private-readiness.outputs.event_base }}" in candidate
    assert 'git merge-base --is-ancestor "$CHECKED_HEAD" HEAD' in candidate
    assert 'git merge-base --is-ancestor "$CHECKED_BASE" HEAD' in candidate


def test_platform_merge_identity_is_not_scanned_as_authored_head(readiness):
    env, runner, _ = readiness
    target = Path(env["GITHUB_WORKSPACE"])
    base = env["TARGET_HEAD_SHA"]
    _git(target, "checkout", "-qb", "authored")
    _git(target, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
         "commit", "--allow-empty", "-qm", "authored change")
    authored = _git(target, "rev-parse", "HEAD")
    _git(target, "checkout", "--detach", base)
    _git(target, "-c", "user.name=GitHub", "-c", "user.email=noreply@github.com",
         "merge", "--no-ff", "authored", "-m", "generated integration")
    integration = _git(target, "rev-parse", "HEAD")
    assert _git(target, "show", "-s", "--format=%cn", integration) == "GitHub"
    assert _git(target, "show", "-s", "--format=%cn", authored) == "Fixture"
    _git(target, "merge-base", "--is-ancestor", authored, integration)
    _git(target, "merge-base", "--is-ancestor", base, integration)
    if os.name != "nt" and shutil.which("bash"):
        _git(target, "remote", "add", "origin", str(target))
        workflow = WORKFLOW.read_text(encoding="utf-8")
        binding = workflow.split("      - name: Bind authored head and immutable integration commit", 1)[1]
        binding = binding.split("      - name: Fetch pinned", 1)[0]
        binding = binding.split("        run: |\n", 1)[1]
        script = "\n".join(line[10:] for line in binding.splitlines())
        bind_env = {**env, "CHECKED_HEAD": authored, "CHECKED_BASE": base,
                    "INTEGRATION_HEAD": integration, "INITIAL_ROOT": "",
                    "EVENT_PR_BASE_SHA": base, "EVENT_PR_HEAD_SHA": authored}
        result = subprocess.run(["bash", "-c", script], cwd=target, env=bind_env, capture_output=True)
        assert result.returncode == 0
        # Direct full inspection may compare a historical/diverged target with
        # the default branch. A pipeline call must retain the ancestor rule.
        _git(target, "checkout", "-qb", "default-advanced", base)
        _git(target, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
             "commit", "--allow-empty", "-qm", "default advanced")
        advanced = _git(target, "rev-parse", "HEAD")
        _git(target, "checkout", "--detach", integration)
        bind_env.update(CHECKED_BASE=advanced, GITHUB_EVENT_NAME="workflow_dispatch", PIPELINE_CALL="false")
        result = subprocess.run(["bash", "-c", script], cwd=target, env=bind_env, capture_output=True)
        assert result.returncode == 0
        bind_env["PIPELINE_CALL"] = "true"
        result = subprocess.run(["bash", "-c", script], cwd=target, env=bind_env, capture_output=True)
        assert result.returncode != 0
        bind_env["INTEGRATION_HEAD"] = "0" * 40
        result = subprocess.run(["bash", "-c", script], cwd=target, env=bind_env, capture_output=True)
        assert result.returncode != 0
    env["TARGET_HEAD_SHA"] = integration
    assert _run(env, runner).returncode == 1
    _git(target, "checkout", "--detach", authored)
    env["TARGET_HEAD_SHA"] = authored
    assert _run(env, runner).returncode == 0


def test_only_root_managed_worktree_output_is_ignored(tmp_path):
    target = tmp_path / "repo"
    _repo(target)
    (target / ".gitignore").write_text((ROOT / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8")
    managed = target / ".worktrees/fixture/source.md"
    managed.parent.mkdir(parents=True)
    managed.write_text("managed checkout output", encoding="utf-8")
    source = target / "content/sources/author.md"
    source.parent.mkdir(parents=True)
    source.write_text("source remains tracked", encoding="utf-8")
    nested = target / "content/.worktrees/source.md"
    nested.parent.mkdir(parents=True)
    nested.write_text("unrelated source path", encoding="utf-8")
    assert _git(target, "check-ignore", str(managed)) == str(managed)
    for file in (source, nested):
        result = subprocess.run(["git", "check-ignore", str(file)], cwd=target, capture_output=True)
        assert result.returncode == 1
        _git(target, "add", str(file))
        assert _git(target, "ls-files", "--error-unmatch", str(file))
