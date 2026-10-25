"""上流失敗の分類、native review 設定、実workflow集約の停止線。"""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import urllib.error

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / ".github/scripts/base_guard_review.py"
spec = importlib.util.spec_from_file_location("base_guard_review", HELPER)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/base-guard.yml").read_text())


def report(protected=False):
    return {"schema": review.SCHEMA, "status": "blocked" if protected else "pass",
            "callers": 1, "findings": ([{"kind": "protected_path_changed",
             "file": ".github/scripts/base_guard_review.py", "job": "", "side": "head"}]
             if protected else [])}


def policy():
    return {"name": review.ENVIRONMENT, "can_admins_bypass": False,
            "deployment_branch_policy": {"protected_branches": True, "custom_branch_policies": False},
            "protection_rules": [{"type": "required_reviewers", "prevent_self_review": False,
             "reviewers": [{"type": "User", "reviewer": {"id": 123, "type": "User"}}]}]}


def test_pass_and_protected_only_classification():
    assert review.classify(report(), 0) is False
    assert review.classify(report(True), 1) is True


@pytest.mark.parametrize("kind", ["unreadable", "foreign_caller", "no_caller", "caller_removed",
    "uses_not_sha", "preflight_ref_missing", "preflight_ref_not_sha", "mismatch",
    "preflight_ref_unreleased", "unknown"])
def test_each_machine_error_mixed_with_protected_changes_is_fatal(kind):
    data = report(True)
    data["findings"].append(dict(data["findings"][0], kind=kind))
    with pytest.raises(review.ReviewError):
        review.classify(data, 1)


@pytest.mark.parametrize("data,code", [
    (None, 0), ({}, 0), ([], 0), (report(), 1), (report(), 2), (report(True), 0),
    (report(True), 2), (dict(report(), schema="v1"), 0), (dict(report(), callers=0), 0),
    (dict(report(), callers=True), 0), (dict(report(), status="absent"), 0),
    (dict(report(True), findings=[]), 1), (dict(report(), extra=True), 0),
    (dict(report(True), findings=[None]), 1),
])
def test_invalid_or_inconsistent_reports_fail_closed(data, code):
    with pytest.raises(review.ReviewError):
        review.classify(data, code)


@pytest.mark.parametrize("change", [{"side": "base"}, {"job": "gate"}, {"file": ""},
                                     {"file": None}, {"extra": 1}])
def test_incomplete_or_base_findings_are_not_approvable(change):
    data = report(True)
    data["findings"][0].update(change)
    with pytest.raises(review.ReviewError):
        review.classify(data, 1)


@pytest.mark.parametrize("raw", ["", "null", "{", '{"status":"pass","status":"blocked"}'])
def test_malformed_json_cannot_pass(raw):
    with pytest.raises(review.ReviewError):
        review.classify(review.read_json(raw), 0)


def test_exact_native_owner_policy():
    review.validate_environment(policy(), 123)


@pytest.mark.parametrize("value", [True, None, "false", 0, {}])
def test_environment_admin_bypass_must_be_explicitly_disabled(value):
    data = policy()
    data["can_admins_bypass"] = value
    with pytest.raises(review.ReviewError):
        review.validate_environment(data, 123)


def test_environment_without_admin_bypass_policy_is_rejected():
    data = policy()
    data.pop("can_admins_bypass")
    with pytest.raises(review.ReviewError):
        review.validate_environment(data, 123)


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(name="other"), lambda p: p.update(deployment_branch_policy=None),
    lambda p: p["deployment_branch_policy"].update(protected_branches=False),
    lambda p: p["deployment_branch_policy"].update(custom_branch_policies=True),
    lambda p: p.update(protection_rules=[]), lambda p: p.update(protection_rules=[None]),
    lambda p: p["protection_rules"].append(deepcopy(p["protection_rules"][0])),
    lambda p: p["protection_rules"][0].update(prevent_self_review=True),
    lambda p: p["protection_rules"][0].pop("prevent_self_review"),
    lambda p: p["protection_rules"][0].update(reviewers=[]),
    lambda p: p["protection_rules"][0]["reviewers"].append({"type": "User"}),
    lambda p: p["protection_rules"][0]["reviewers"][0].update(type="Team"),
    lambda p: p["protection_rules"][0]["reviewers"][0]["reviewer"].update(id=124),
    lambda p: p["protection_rules"][0]["reviewers"][0]["reviewer"].update(id=True),
])
def test_missing_or_weakened_environment_fails(mutation):
    data = policy()
    mutation(data)
    with pytest.raises(review.ReviewError):
        review.validate_environment(data, 123)


def test_api_error_is_bounded_and_fixed_endpoint_has_no_token(monkeypatch):
    def open_request(request, timeout):
        assert request.full_url == "https://api.github.com/repos/owner/repo/environments/ci-protected-change-review"
        assert "private-token" not in request.full_url
        assert timeout == 30
        raise urllib.error.URLError("private-token")
    monkeypatch.setattr(review.urllib.request, "build_opener", lambda *a: SimpleNamespace(open=open_request))
    with pytest.raises(review.ReviewError, match="^environment_api_failed$"):
        review.fetch_environment("owner/repo", "private-token")


def test_api_redirect_is_never_followed():
    with pytest.raises(review.ReviewError):
        review._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid")


@pytest.mark.parametrize("repository", ["owner/repo?token=x", "owner/repo/else", "https://evil", "owner/repo\n"])
def test_repository_cannot_change_api_endpoint(repository):
    with pytest.raises(review.ReviewError):
        review.fetch_environment(repository, "token")


@pytest.mark.parametrize("inspect,required,approval,ok", [
    ("success", "false", "skipped", True), ("success", "true", "success", True),
    ("success", "true", "skipped", False), ("success", "true", "failure", False),
    ("success", "true", "cancelled", False), ("success", "true", "timed_out", False),
    ("success", "true", "rejected", False), ("success", "", "success", False),
    ("success", "false", "success", False), ("failure", "true", "success", False),
    ("cancelled", "false", "skipped", False), ("skipped", "false", "skipped", False),
    ("", "false", "skipped", False), ("success", "unknown", "success", False),
])
def test_real_aggregate_shell(inspect, required, approval, ok):
    script = WORKFLOW["jobs"]["base-guard"]["steps"][0]["run"]
    result = subprocess.run(["bash", "-c", script], capture_output=True,
        env=dict(os.environ, INSPECT_RESULT=inspect, REVIEW_REQUIRED=required, REVIEW_RESULT=approval))
    assert (result.returncode == 0) is ok


@pytest.mark.parametrize("required", [False, True])
def test_inspect_executes_upstream_and_only_emits_output_after_policy_validation(tmp_path, monkeypatch, required):
    data = report(required)
    if required:
        data["findings"][0]["file"] = '.github/a\n::warning::bad<script>.yml'
    args = SimpleNamespace(repo="target", tool="tool", base="a" * 40, head="b" * 40,
        pr="9", repository="owner/repo", owner_id="123", owner_type="User")
    output, summary = tmp_path / "output", tmp_path / "summary"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("REVIEW_API_TOKEN", "private-token")
    def run(command, **kwargs):
        assert command == [sys.executable, "-I", "tool/scripts/base_guard.py", "--repo", "target",
            "--base-ref", "a" * 40, "--head-ref", "b" * 40, "--trusted-tool", "tool", "--json"]
        assert "REVIEW_API_TOKEN" not in os.environ
        return SimpleNamespace(stdout=json.dumps(data).encode(), returncode=int(required))
    monkeypatch.setattr(review.subprocess, "run", run)
    calls = []
    monkeypatch.setattr(review, "fetch_environment", lambda *a: calls.append(a) or policy())
    review.inspect(args)
    assert output.read_text() == f"review_required={str(required).lower()}\n"
    assert bool(calls) is required
    assert "<script>" not in summary.read_text()
    assert "\n::warning" not in summary.read_text()
    output.unlink()
    if required:
        monkeypatch.setattr(review, "fetch_environment", lambda *a: {})
        with pytest.raises(review.ReviewError):
            review.inspect(args)
        assert not output.exists()


def test_workflow_preserves_base_only_execution_pins_and_native_authority():
    jobs = WORKFLOW["jobs"]
    inspect = jobs["inspect"]
    assert inspect["permissions"] == {"contents": "read", "actions": "read"}
    assert inspect["env"]["PREFLIGHT_REF"] == "5b7c774deb8e9abcf0fce0c5f39ec1c1f3a894f3"
    checkouts = [s["with"] for s in inspect["steps"] if s.get("uses", "").startswith("actions/checkout@")]
    assert checkouts[0]["ref"] == "${{ github.event.pull_request.base.sha }}"
    assert all(s["persist-credentials"] is False for s in checkouts)
    text = (ROOT / ".github/workflows/base-guard.yml").read_text()
    for guard in ('tag --list "v[0-9]*" --contains', "--require-hashes", "python -I target/.github/scripts/base_guard_review.py"):
        assert guard in text
    assert "continue-on-error" not in text and "secrets." not in text
    assert jobs["owner-review"]["permissions"] == {}
    assert jobs["owner-review"]["environment"]["name"] == review.ENVIRONMENT
    assert "head.sha" in jobs["owner-review"]["name"]
    assert "needs.inspect.result == 'success'" in jobs["owner-review"]["if"]
    assert "needs.inspect.outputs.review_required == 'true'" in jobs["owner-review"]["if"]
    assert jobs["base-guard"]["if"] == "${{ always() }}"
    assert jobs["base-guard"]["needs"] == ["inspect", "owner-review"]


def test_actual_pinned_upstream_protects_helper_only_change(tmp_path):
    # 上流sourceを複製せず、検証時だけ指定された固定checkoutを実行する。
    tool = os.environ.get("NPS_TEST_BASE_GUARD_TOOL")
    if not tool:
        pytest.skip("固定した repo-preflight checkout を指定した検証で実行")
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()
    git("init", "-q")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    workflow = tmp_path / ".github/workflows/preflight.yml"
    workflow.parent.mkdir(parents=True)
    pin = "5b7c774deb8e9abcf0fce0c5f39ec1c1f3a894f3"
    workflow.write_text(f"jobs:\n  gate:\n    uses: nexus-ai-2045/repo-preflight/.github/workflows/preflight-gate.yml@{pin}\n    with:\n      preflight-ref: {pin}\n")
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    helper = tmp_path / ".github/scripts/base_guard_review.py"
    helper.parent.mkdir()
    helper.write_text("raise RuntimeError('candidate code must never execute')\n")
    git("add", ".")
    git("commit", "-qm", "helper only")
    result = subprocess.run([sys.executable, "-I", str(Path(tool) / "scripts/base_guard.py"),
        "--repo", str(tmp_path), "--base-ref", base, "--head-ref", "HEAD", "--json"], capture_output=True)
    assert review.classify(review.read_json(result.stdout), result.returncode) is True
    assert review.read_json(result.stdout)["findings"] == report(True)["findings"]
