#!/usr/bin/env python3
"""Fail PR checks when package changes do not bump package.yaml version."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_METADATA_FILES = {
    "package.yaml",
    "README.md",
    "README.rendered.html",
    "CHANGELOG.md",
}


def run_git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout.strip()


def parse_version(text: str) -> tuple[int, int, int]:
    match = re.search(r"(?m)^version:\s*([0-9]+)\.([0-9]+)\.([0-9]+)\s*$", text)
    if not match:
        raise ValueError("package.yaml semantic version is missing")
    return tuple(int(part) for part in match.groups())


def changed_files(base_ref: str) -> list[str]:
    diff = run_git("diff", "--name-only", f"{base_ref}...HEAD")
    return [line.strip() for line in diff.splitlines() if line.strip()]


def requires_version_bump(paths: list[str]) -> bool:
    return any(path not in VERSION_METADATA_FILES for path in paths)


def load_base_package(base_ref: str) -> str:
    return run_git("show", f"{base_ref}:package.yaml")


def resolve_base_ref() -> str | None:
    explicit = os.environ.get("VERSION_BUMP_BASE_REF")
    if explicit:
        return explicit
    github_base_ref = os.environ.get("GITHUB_BASE_REF")
    if github_base_ref:
        remote_ref = f"origin/{github_base_ref}"
        run_git("fetch", "--quiet", "origin", github_base_ref, check=False)
        if run_git("rev-parse", "--verify", remote_ref, check=False):
            return remote_ref
        return github_base_ref
    return None


def main() -> int:
    base_ref = resolve_base_ref()
    if not base_ref:
        print("version_bump_check=skipped_no_base_ref")
        return 0

    paths = changed_files(base_ref)
    if not paths:
        print("version_bump_check=ok_no_changes")
        return 0

    current_version = parse_version((ROOT / "package.yaml").read_text(encoding="utf-8"))
    base_version = parse_version(load_base_package(base_ref))

    if requires_version_bump(paths) and current_version <= base_version:
        print(
            "version_bump_check=failed_package_changed_without_version_bump",
            file=sys.stderr,
        )
        print(f"base_version={'.'.join(map(str, base_version))}", file=sys.stderr)
        print(f"current_version={'.'.join(map(str, current_version))}", file=sys.stderr)
        print("changed_files=" + ",".join(paths), file=sys.stderr)
        return 1

    print("version_bump_check=ok")
    print(f"base_version={'.'.join(map(str, base_version))}")
    print(f"current_version={'.'.join(map(str, current_version))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
