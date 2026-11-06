#!/usr/bin/env python3
"""共通selectorを呼び、NPS所有の環境別pytestだけをargvで実行する。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import subprocess
import sys
import tempfile

NATIVE_WINDOWS_TEST = "tests/test_windows_skill_installer.py"


def package_version_only(repo: Path, base: str) -> dict | None:
    """Recognize only one root version line with every other byte unchanged."""
    package = repo / "package.yaml"
    if package.is_symlink() or not package.is_file():
        return None
    tree = subprocess.check_output(
        ["git", "ls-tree", base, "--", "package.yaml"], cwd=repo, text=True
    ).split()
    mode = "100755" if package.stat().st_mode & 0o111 else "100644"
    if len(tree) != 4 or tree[0] != mode or tree[1] != "blob":
        return None
    before = subprocess.check_output(["git", "show", base + ":package.yaml"], cwd=repo)
    current = package.read_bytes()
    if before == current:
        return None
    version_line = re.compile(rb"(?m)^version:[ \t]*([0-9]+\.[0-9]+\.[0-9]+)[ \t]*(?=\r?$)")
    root_key = re.compile(rb"(?m)^(?:version|\"version\"|'version')[ \t]*:")
    matches = [list(version_line.finditer(data)) for data in (before, current)]
    if any(len(found) != 1 for found in matches) or any(
        len(root_key.findall(data)) != 1 for data in (before, current)
    ):
        return None
    if version_line.sub(b"version: <metadata>", before) != version_line.sub(
        b"version: <metadata>", current
    ):
        return None
    guard = Path(__file__).with_name("check_version_bump.py")
    if guard.is_symlink() or not guard.is_file():
        raise ValueError("version parser must be a regular file")
    guard_bytes = guard.read_bytes()
    namespace = {"__name__": "_nps_version_guard", "__file__": str(guard)}
    exec(compile(guard_bytes, str(guard), "exec"), namespace)
    try:
        versions = [namespace["parse_version"](data.decode("utf-8")) for data in (before, current)]
    except (ValueError, UnicodeError):
        return None
    return {"base_package_sha256": hashlib.sha256(before).hexdigest(),
            "current_package_sha256": hashlib.sha256(current).hexdigest(),
            "base_version": list(versions[0]), "current_version": list(versions[1]),
            "version_guard_sha256": hashlib.sha256(guard_bytes).hexdigest()}


def verify_version_sources(repo: Path, binding: dict) -> None:
    """Do not execute a plan after any input to its owner condition changed."""
    if not binding.get("package_version_only"):
        return
    for path, expected in (
        (repo / "package.yaml", binding["current_package_sha256"]),
        (repo / ".test-selection.json", binding["original_policy_sha256"]),
        (Path(__file__).with_name("check_version_bump.py"), binding["version_guard_sha256"]),
    ):
        if (path.is_symlink() or not stat.S_ISREG(path.stat().st_mode)
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
            raise ValueError("version metadata inputs changed before execution")


@contextmanager
def selection_policy(repo: Path, base: str):
    """Bind the owner metadata condition before passing a private policy to Core."""
    original = repo / ".test-selection.json"
    source = original.read_bytes()
    policy = json.loads(source)
    if not isinstance(policy, dict) or not isinstance(policy.get("rules", []), list):
        raise ValueError("selection policy rules must be a list")
    for rule in policy.get("rules", []):
        if not isinstance(rule, dict) or not rule.get("changes"):
            raise ValueError("selection policy rules require changes")
        for key in ("changes", "tests", "checks"):
            values = rule.get(key, [])
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise ValueError("selection policy rule paths and check IDs must be lists")
        if (rule.get("dependency_mode", "auto") not in ("auto", "mapped", "supplement")
                or ("no_tests" in rule and not isinstance(rule["no_tests"], bool))
                or any(not value.strip() or value != value.strip() for value in rule.get("checks", []))):
            raise ValueError("selection policy rule mode or check IDs are invalid")
    evidence = {"original_policy_sha256": hashlib.sha256(source).hexdigest(),
                "effective_policy_sha256": hashlib.sha256(source).hexdigest(),
                "package_version_only": False, "comparison_base": base}
    metadata = package_version_only(repo, base)
    owners = [rule for rule in policy.get("rules", [])
              if "package.yaml" in rule.get("changes", [])]
    if metadata is None or not owners:
        yield original, evidence
        return
    # Retain the existing owner package contracts; only the evaluated version
    # line leaves automatic closure. All other package changes keep auto mode.
    tests = {"tests/test_docs_sync_check.py"}
    checks = set()
    for rule in owners:
        tests.update(rule.get("tests", []))
        checks.update(rule.get("checks", []))
        rule["changes"] = [path for path in rule["changes"] if path != "package.yaml"]
    policy["rules"] = [rule for rule in policy["rules"] if rule.get("changes")]
    policy["rules"].append({"changes": ["package.yaml"], "dependency_mode": "mapped",
                            "tests": sorted(tests), "checks": sorted(checks)})
    effective = (json.dumps(policy, ensure_ascii=False, indent=2) + "\n").encode()
    evidence.update(metadata, package_version_only=True,
                    effective_policy_sha256=hashlib.sha256(effective).hexdigest())
    cache = repo / ".pytest_cache"
    if cache.is_symlink():
        raise ValueError("selection policy cache must not be a symlink")
    cache.mkdir(exist_ok=True)
    cache.resolve().relative_to(repo.resolve())
    if subprocess.run(["git", "check-ignore", "--quiet", "--",
                       ".pytest_cache/nps-selection-policy-probe.json"], cwd=repo).returncode:
        raise ValueError("selection policy cache must be ignored")
    with tempfile.TemporaryDirectory(prefix="nps-selection-", dir=cache) as directory:
        path = Path(directory) / "policy.json"
        path.write_bytes(effective)
        yield path, evidence


def display_value(value, repo: Path, selector: Path):
    """Keep execution argv separate from portable receipts and local logs."""
    replacements = ((str(selector.resolve()), "<selector>"), (str(repo.resolve()), "<repo>"),
                    (sys.executable, "<python>"), (str(Path.home()), "<home>"))
    if isinstance(value, str):
        for source, target in replacements:
            value = value.replace(source, target)
        return value
    if isinstance(value, list):
        return [display_value(item, repo, selector) for item in value]
    if isinstance(value, dict):
        return {key: display_value(item, repo, selector) for key, item in value.items()}
    return value


def receipt_text(value, repo: Path, selector: Path) -> str:
    return json.dumps(display_value(value, repo, selector), ensure_ascii=False, indent=2) + "\n"


def test_command(repo: Path, plan: dict, environment: str) -> list[str] | None:
    if (plan.get("schema") != "test-selection/v1"
            or plan.get("status") not in {"selected", "no_tests"}
            or plan.get("unresolved") or plan.get("checks")):
        raise ValueError("unresolved plan or required check ID without a consumer dispatcher")
    tests = plan.get("selected_tests")
    if not isinstance(tests, list) or not all(isinstance(p, str) for p in tests):
        raise ValueError("selected_tests must be a list of test file paths")
    for name in tests:
        path = PurePosixPath(name)
        if (path.is_absolute() or PureWindowsPath(name).drive or ".." in path.parts
                or "\\" in name or not name.startswith(("tests/", "scripts/"))
                or path.suffix != ".py" or not path.name.startswith("test_")):
            raise ValueError("selected test must be an owned relative Python test file")
        (repo / path).resolve().relative_to(repo.resolve())
        if not (repo / path).is_file():
            raise ValueError("selected test file is missing")
    selected = [p for p in tests if (p == NATIVE_WINDOWS_TEST) == (environment == "windows")]
    return [sys.executable, "-m", "pytest", "-q", "--", *selected] if selected else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selector-script", required=True, type=Path)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--environment", choices=("python", "windows"), default="python")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    binding = {}
    try:
        # Plan is produced fresh for this target/base/policy; no replay of an unbound input plan.
        comparison_base = subprocess.check_output(
            ["git", "merge-base", args.base_ref, "HEAD"], cwd=repo, text=True).strip()
        binding = {"repo": str(repo), "base_ref": args.base_ref,
                   "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
                   "base_commit": subprocess.check_output(["git", "rev-parse", "--verify", args.base_ref + "^{commit}"], cwd=repo, text=True).strip(),
                   "policy_file_sha256": hashlib.sha256((repo / ".test-selection.json").read_bytes()).hexdigest(),
                   "selector_sha256": hashlib.sha256(args.selector_script.resolve().read_bytes()).hexdigest()}
        with selection_policy(repo, comparison_base) as (policy, metadata):
            binding.update(metadata)
            verify_version_sources(repo, binding)
            command = [sys.executable, str(args.selector_script.resolve()), "--repo", str(repo),
                       "--base-ref", comparison_base, "--selection-config", str(policy),
                       "--plan-tests", "--json"]
            result = subprocess.run(command, cwd=repo, capture_output=True, text=True, encoding="utf-8", check=False)
            verify_version_sources(repo, binding)
        if result.returncode:
            if args.receipt:
                args.receipt.parent.mkdir(parents=True, exist_ok=True)
                args.receipt.write_text(receipt_text({"binding": binding, "executed": False,
                    "selector_exit_code": result.returncode, "selector_stdout": result.stdout,
                    "selector_stderr": result.stderr}, repo, args.selector_script), encoding="utf-8")
            print(display_value(result.stdout, repo, args.selector_script), end="")
            print(display_value(result.stderr, repo, args.selector_script), end="", file=sys.stderr)
            return result.returncode
        plan = json.loads(result.stdout)
        pytest_command = test_command(repo, plan, args.environment)
        receipt = {"plan": plan, "binding": binding, "environment": args.environment, "selector_command": command,
                   "pytest_command": pytest_command, "executed": False}
        if not args.plan_only and pytest_command:
            verify_version_sources(repo, binding)
            receipt["pytest_exit_code"] = subprocess.run(pytest_command, cwd=repo).returncode
            receipt["executed"] = True
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(receipt_text(receipt, repo, args.selector_script), encoding="utf-8")
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as output:
                output.write(f"native_required={str(NATIVE_WINDOWS_TEST in plan['selected_tests']).lower()}\n")
        print(receipt_text(receipt, repo, args.selector_script), end="")
        return receipt.get("pytest_exit_code", 0)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(receipt_text({"status": "unresolved", "executed": False,
                "binding": binding, "error": str(exc)}, repo, args.selector_script), encoding="utf-8")
        print("停止: " + display_value(str(exc), repo, args.selector_script), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
