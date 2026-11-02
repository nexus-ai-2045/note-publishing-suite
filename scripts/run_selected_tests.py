#!/usr/bin/env python3
"""共通selectorを呼び、NPS所有の環境別pytestだけをargvで実行する。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess
import sys

NATIVE_WINDOWS_TEST = "tests/test_windows_skill_installer.py"


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
    try:
        # Plan is produced fresh for this target/base/policy; no replay of an unbound input plan.
        command = [sys.executable, str(args.selector_script.resolve()), "--repo", str(repo),
                   "--base-ref", args.base_ref, "--selection-config", ".test-selection.json",
                   "--plan-tests", "--json"]
        binding = {"repo": str(repo), "base_ref": args.base_ref,
                   "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
                   "base_commit": subprocess.check_output(["git", "rev-parse", "--verify", args.base_ref + "^{commit}"], cwd=repo, text=True).strip(),
                   "policy_file_sha256": hashlib.sha256((repo / ".test-selection.json").read_bytes()).hexdigest(),
                   "selector_sha256": hashlib.sha256(args.selector_script.resolve().read_bytes()).hexdigest()}
        result = subprocess.run(command, cwd=repo, capture_output=True, text=True, encoding="utf-8", check=False)
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
                "error": str(exc)}, repo, args.selector_script), encoding="utf-8")
        print("停止: " + display_value(str(exc), repo, args.selector_script), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
