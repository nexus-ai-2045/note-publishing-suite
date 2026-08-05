#!/usr/bin/env python3
"""Check generated and handwritten documentation without modifying the repository."""

from __future__ import annotations

import argparse
import difflib
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_KEY = "docs_sync_contract: |"


class ContractError(ValueError):
    """Raised when the embedded docs-sync contract is invalid."""


def load_contract(package_path: Path) -> dict[str, Any]:
    lines = package_path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line == CONTRACT_KEY)
    except StopIteration as exc:
        raise ContractError("package.yaml is missing docs_sync_contract") from exc

    payload: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("  "):
            payload.append(line[2:])
            continue
        if not line.strip() and payload:
            payload.append("")
            continue
        break
    try:
        contract = json.loads("\n".join(payload))
    except json.JSONDecodeError as exc:
        raise ContractError(f"docs_sync_contract is not valid JSON: {exc}") from exc
    if not isinstance(contract, dict) or contract.get("version") != 1:
        raise ContractError("docs_sync_contract version must be 1")
    for field in ("generated", "required_docs", "path_rules"):
        if not isinstance(contract.get(field), list):
            raise ContractError(f"docs_sync_contract.{field} must be a list")
    return contract


def run_git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout.strip()


def resolve_base_ref(root: Path, explicit: str | None) -> str | None:
    candidates = [explicit]
    github_base = os.environ.get("GITHUB_BASE_REF")
    if github_base:
        candidates.extend([f"origin/{github_base}", github_base])
    candidates.append("HEAD^")
    for candidate in candidates:
        if candidate and run_git(root, "rev-parse", "--verify", candidate, check=False):
            return candidate
    return None


def changed_files(root: Path, base_ref: str | None) -> set[str]:
    changed: set[str] = set()
    if base_ref:
        output = run_git(root, "diff", "--name-only", f"{base_ref}...HEAD")
        changed.update(line for line in output.splitlines() if line)
    for args in (("diff", "--name-only", "HEAD"), ("diff", "--cached", "--name-only")):
        output = run_git(root, *args)
        changed.update(line for line in output.splitlines() if line)
    untracked = run_git(root, "ls-files", "--others", "--exclude-standard")
    changed.update(line for line in untracked.splitlines() if line)
    return changed


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def no_update_reason(review_text: str) -> str | None:
    marker = "更新不要。理由:"
    for line in review_text.splitlines():
        if marker not in line:
            continue
        reason = line.split(marker, 1)[1].strip().strip("<> ")
        if len(reason) >= 8:
            return reason
    return None


def check_required_docs(root: Path, contract: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"code": "missing_required_doc", "path": path}
        for path in contract["required_docs"]
        if not (root / path).is_file()
    ]


def check_handwritten_docs(
    changed: set[str], contract: dict[str, Any], review_text: str
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    reason = no_update_reason(review_text)
    for rule in contract["path_rules"]:
        patterns = rule.get("patterns", [])
        docs = set(rule.get("docs", []))
        triggers = sorted(path for path in changed if matches(path, patterns))
        if triggers and not (docs & changed) and reason is None:
            issues.append(
                {
                    "code": "missing_doc_review",
                    "path": triggers[0],
                    "expected": ",".join(sorted(docs)),
                }
            )
    return issues


def render_in_temporary_tree(root: Path, source: str, renderer: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="note-docs-sync-") as tmp_name:
        tmp = Path(tmp_name)
        (tmp / source).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / source, tmp / source)
        (tmp / renderer).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / renderer, tmp / renderer)
        result = subprocess.run(
            [sys.executable, renderer], cwd=tmp, text=True, capture_output=True, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout + result.stderr)
        output = tmp / "README.rendered.html"
        if not output.is_file():
            raise RuntimeError("renderer did not create README.rendered.html")
        return output.read_bytes()


def check_generated(
    root: Path, contract: dict[str, Any]
) -> tuple[list[dict[str, str]], str]:
    issues: list[dict[str, str]] = []
    patches: list[str] = []
    for item in contract["generated"]:
        source = item.get("source")
        output = item.get("output")
        renderer = item.get("renderer")
        if not all(isinstance(value, str) and value for value in (source, output, renderer)):
            raise ContractError("generated entries require source, output, and renderer")
        expected = render_in_temporary_tree(root, source, renderer)
        actual_path = root / output
        actual = actual_path.read_bytes() if actual_path.is_file() else b""
        if expected == actual:
            continue
        issues.append({"code": "generated_drift", "path": output})
        patches.extend(
            difflib.unified_diff(
                actual.decode("utf-8").splitlines(keepends=True),
                expected.decode("utf-8").splitlines(keepends=True),
                fromfile=f"a/{output}",
                tofile=f"b/{output}",
            )
        )
    return issues, "".join(patches)


def fix_generated(root: Path, contract: dict[str, Any]) -> None:
    for item in contract["generated"]:
        result = subprocess.run(
            [sys.executable, item["renderer"]],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout + result.stderr)


def write_output(path: str | None, content: str) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref")
    parser.add_argument("--review-file")
    parser.add_argument("--json-out")
    parser.add_argument("--patch-out")
    parser.add_argument("--fix-generated", action="store_true")
    args = parser.parse_args()

    try:
        contract = load_contract(ROOT / "package.yaml")
        if args.fix_generated:
            fix_generated(ROOT, contract)
        base_ref = resolve_base_ref(ROOT, args.base_ref)
        changed = changed_files(ROOT, base_ref)
        review_text = ""
        if args.review_file and Path(args.review_file).is_file():
            review_text = Path(args.review_file).read_text(encoding="utf-8")
        issues = check_required_docs(ROOT, contract)
        handwritten = check_handwritten_docs(changed, contract, review_text)
        generated, patch = check_generated(ROOT, contract)
        issues.extend(handwritten)
        issues.extend(generated)
        state = "ok" if not issues else issues[0]["code"]
        result = {
            "ok": not issues,
            "state": state,
            "base_ref": base_ref,
            "changed_files": sorted(changed),
            "issues": issues,
            "repository_modified": False,
            "external_actions_performed": [],
        }
    except (ContractError, RuntimeError, OSError) as exc:
        patch = ""
        result = {
            "ok": False,
            "state": "contract_invalid" if isinstance(exc, ContractError) else "renderer_failed",
            "issues": [{"code": type(exc).__name__, "message": str(exc)}],
            "repository_modified": False,
            "external_actions_performed": [],
        }

    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    write_output(args.json_out, serialized)
    write_output(args.patch_out, patch)
    print(serialized, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
