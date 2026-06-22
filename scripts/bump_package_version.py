#!/usr/bin/env python3
"""Bump package.yaml version and keep public version metadata in sync."""

from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def parse_version(text: str) -> tuple[int, int, int]:
    match = re.search(r"(?m)^version:\s*([0-9]+)\.([0-9]+)\.([0-9]+)\s*$", text)
    if not match:
        raise ValueError("package.yaml semantic version is missing")
    return tuple(int(part) for part in match.groups())


def format_version(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def bump_version(version: tuple[int, int, int], part: str) -> tuple[int, int, int]:
    major, minor, patch = version
    if part == "major":
        return major + 1, 0, 0
    if part == "minor":
        return major, minor + 1, 0
    if part == "patch":
        return major, minor, patch + 1
    raise ValueError(f"unknown version part: {part}")


def replace_once(text: str, old: str, new: str, path: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{path} expected one occurrence of {old!r}, found {count}")
    return text.replace(old, new, 1)


def build_changelog_section(
    version: str,
    date: str,
    changes: list[str],
    verifications: list[str],
) -> str:
    change_lines = "\n".join(f"- {item}" for item in changes)
    verification_lines = "\n".join(f"- `{item}`" for item in verifications)
    return (
        f"## {version}\n\n"
        f"日付: {date}\n\n"
        "変更:\n"
        f"{change_lines}\n\n"
        "検証:\n"
        f"{verification_lines}\n\n"
        "公開境界:\n"
        "- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。\n"
        "- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。\n"
    )


def insert_changelog_section(changelog: str, section: str) -> str:
    match = re.search(r"(?m)^## \d+\.\d+\.\d+\s*$", changelog)
    if not match:
        raise ValueError("CHANGELOG.md has no version section")
    return changelog[: match.start()] + section + "\n" + changelog[match.start() :]


def update_files(
    part: str,
    date: str,
    changes: list[str],
    verifications: list[str],
    dry_run: bool,
) -> tuple[str, str]:
    package = read("package.yaml")
    old_version = format_version(parse_version(package))
    new_version = format_version(bump_version(parse_version(package), part))

    updates = {
        "package.yaml": re.sub(
            r"(?m)^version:\s*[0-9]+\.[0-9]+\.[0-9]+\s*$",
            f"version: {new_version}",
            package,
            count=1,
        ),
        "README.md": replace_once(
            read("README.md"),
            f"パッケージ版: `{old_version}`",
            f"パッケージ版: `{new_version}`",
            "README.md",
        ),
        "README.rendered.html": replace_once(
            read("README.rendered.html"),
            f"パッケージ版: <code>{old_version}</code>",
            f"パッケージ版: <code>{new_version}</code>",
            "README.rendered.html",
        ),
        "CHANGELOG.md": insert_changelog_section(
            read("CHANGELOG.md"),
            build_changelog_section(new_version, date, changes, verifications),
        ),
    }

    if not dry_run:
        for path, text in updates.items():
            write(path, text)
    return old_version, new_version


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bump package version and update README/CHANGELOG metadata."
    )
    parser.add_argument("--part", choices=["patch", "minor", "major"], default="patch")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--change", action="append", required=True)
    parser.add_argument(
        "--verification",
        action="append",
        default=["python -m pytest scripts/test_skill_integration.py tests -q"],
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    old_version, new_version = update_files(
        args.part,
        args.date,
        args.change,
        args.verification,
        args.dry_run,
    )
    print("version_bump=ok")
    print(f"old_version={old_version}")
    print(f"new_version={new_version}")
    if args.dry_run:
        print("dry_run=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
