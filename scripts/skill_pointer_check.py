#!/usr/bin/env python3
"""Fail closed when Claude Code pointer skills reference missing package SSOT files."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_ROOT = ROOT / "adapters" / "claude-code"
PACKAGE_TARGET_RE = re.compile(r"\{\{PACKAGE_ROOT\}\}(/[^`\r\n]*SKILL\.md)")
INSTALLED_TARGET_RE = re.compile(
    r"(?<![^\s`])(?:\$\{[^}]+\}|\$[A-Za-z_]\w*|~[^/\s`]*|[A-Za-z]:)?[\\/][^`\r\n]*SKILL\.md(?=[`\s]|$)"
)


def normalized_target(raw_target: str) -> Path:
    """既知hostroot・HOME表記とnative Windows/MSYS絶対pathだけを解決する。"""
    for prefix in ("${NPS_PACKAGE_ROOT}/", "$NPS_PACKAGE_ROOT/"):
        if raw_target.startswith(prefix):
            host_root = os.environ.get("NPS_PACKAGE_ROOT", str(ROOT))
            if (not host_root.strip() or any(char in host_root for char in ("$", "`"))
                    or any(ord(char) < 32 or ord(char) == 127 for char in host_root)
                    or not (host_root.startswith("/") or re.match(r"[A-Za-z]:[\\/]", host_root))):
                raise ValueError("NPS_PACKAGE_ROOTには変数や式を含まない絶対pathが必要です")
            raw_target = host_root.rstrip("/\\") + "/" + raw_target[len(prefix):]
            break
    for prefix in ("${HOME}/", "$HOME/", "~/"):
        if raw_target.startswith(prefix):
            raw_target = str(Path.home() / raw_target[len(prefix):])
            break
    if any(char in raw_target for char in ("$", "`")) or raw_target.startswith("~"):
        raise ValueError("unsupported portable SSOT target")
    if not (raw_target.startswith("/") or re.match(r"[A-Za-z]:[\\/]", raw_target)):
        raise ValueError("SSOT target must be absolute")
    if os.name == "nt" and re.fullmatch(r"/[A-Za-z]/.*", raw_target):
        raw_target = f"{raw_target[1]}:{raw_target[2:]}"
    elif os.name == "nt" and re.fullmatch(r"/mnt/[A-Za-z]/.*", raw_target):
        raw_target = f"{raw_target[5]}:{raw_target[6:]}"
    return Path(raw_target).resolve(strict=False)


def installed_target_candidates(text: str) -> list[str]:
    """code領域または単独行を全体で読み、式の内部pathへfallbackしない。"""
    candidates: list[str] = []

    def fenced(match: re.Match[str]) -> str:
        content = match.group(1).strip()
        if "SKILL.md" in content:
            candidates.append(content.removeprefix("Read: "))
        return "\n" * match.group(0).count("\n")

    remainder = re.sub(r"^```[^\n]*\n(.*?)^```[ \t]*$", fenced, text, flags=re.M | re.S)

    def inline(match: re.Match[str]) -> str:
        content = match.group(1)
        if "SKILL.md" in content:
            candidates.append(content.strip())
        return ""

    remainder = re.sub(r"`([^`\r\n]+)`", inline, remainder)
    candidates.extend(line.strip() for line in remainder.splitlines()
                      if re.search(r"[/\\][^\r\n]*SKILL\.md", line))
    return candidates


def adapter_names() -> list[str]:
    return sorted(path.parent.name for path in ADAPTER_ROOT.glob("*/SKILL.md"))


def expected_package_target(name: str, package_root: Path | None = None) -> Path:
    package_root = ROOT if package_root is None else package_root
    if name == "note-publishing-suite":
        return package_root / "SKILL.md"
    return package_root / "skills" / name / "SKILL.md"


def installed_package_roots() -> dict[str, Path]:
    """現在checkoutと、Git common dirで同一性を検証したprimaryだけを返す。"""
    roots = {"current_checkout": ROOT.resolve()}
    # hookが渡すrepository局所環境を別checkoutのGit呼出しへ持ち込まない。
    # GIT_CONFIG_*もcore.worktree等を注入できるため、子環境だけから除外する。
    repository_variables = {
        "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_OBJECT_DIRECTORY", "GIT_DIR",
        "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE", "GIT_INDEX_FILE",
        "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX",
        "GIT_SHALLOW_FILE", "GIT_COMMON_DIR", "GIT_CEILING_DIRECTORIES",
        "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    }
    git_env = {key: value for key, value in os.environ.items()
               if key not in repository_variables and not key.startswith("GIT_CONFIG")}

    def git_path(directory: Path, argument: str) -> Path:
        result = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--path-format=absolute", argument],
            text=True, encoding="utf-8", capture_output=True, check=True, timeout=5, env=git_env,
        )
        value = result.stdout.strip()
        if not value or "\n" in value or not Path(value).is_absolute():
            raise ValueError("Git root must be one absolute path")
        return Path(value)

    try:
        if git_path(ROOT, "--show-toplevel") != roots["current_checkout"]:
            return roots
        common = git_path(ROOT, "--git-common-dir")
        primary = common.parent
        # linked worktree管理領域やbare repositoryをprimaryと誤認しない。
        if (common.name != ".git" or not common.is_dir() or common.is_symlink()
                or not (primary / "SKILL.md").is_file()
                or (primary / "SKILL.md").is_symlink()
                or git_path(primary, "--show-toplevel") != primary
                or git_path(primary, "--git-common-dir") != common):
            return roots
        if primary != roots["current_checkout"]:
            roots["primary_canonical"] = primary
    except (OSError, ValueError, subprocess.SubprocessError):
        pass  # Gitのない配布物も従来どおり現在checkoutだけを検査する。
    return roots


def validate_templates() -> tuple[list[str], list[str]]:
    checked: list[str] = []
    errors: list[str] = []
    for template in sorted(ADAPTER_ROOT.glob("*/SKILL.md")):
        name = template.parent.name
        expected = expected_package_target(name)
        text = template.read_text(encoding="utf-8")
        suffixes = PACKAGE_TARGET_RE.findall(text)
        targets = [ROOT / suffix.lstrip("/") for suffix in suffixes]
        if not targets:
            errors.append(f"{template.relative_to(ROOT)}: package SSOT pointer not found")
            continue
        checked.extend(str(target) for target in targets)
        if targets != [expected]:
            errors.append(
                f"{template.relative_to(ROOT)}: unexpected package SSOT target; "
                f"expected {expected}"
            )
            continue
        if not expected.is_file():
            errors.append(f"missing package SSOT target: {expected}")
    return checked, errors


def validate_installed(installed_root: Path) -> tuple[list[str], list[str]]:
    checked: list[str] = []
    errors: list[str] = []
    package_roots = installed_package_roots()
    selected_kind: str | None = None
    for name in adapter_names():
        pointer = installed_root / name / "SKILL.md"
        if pointer.parent.is_symlink():
            errors.append(f"installed pointer directory must not be a symlink: {pointer.parent}")
            continue
        if pointer.is_symlink():
            errors.append(f"installed pointer must not be a symlink: {pointer}")
            continue
        if not pointer.is_file():
            errors.append(f"missing installed pointer: {pointer}")
            continue
        pointer_text = pointer.read_text(encoding="utf-8")
        targets = installed_target_candidates(pointer_text)
        if any(INSTALLED_TARGET_RE.fullmatch(target) is None for target in targets):
            errors.append(f"installed pointer has no absolute SSOT target: {pointer}; unsupported path expression")
            continue
        if not targets:
            errors.append(f"installed pointer has no absolute SSOT target: {pointer}")
            continue
        try:
            parsed_targets = [normalized_target(raw_target) for raw_target in targets]
        except ValueError as exc:
            errors.append(f"invalid installed SSOT target: {pointer}; {exc}")
            continue
        checked.extend(str(target) for target in parsed_targets)
        if len(parsed_targets) == 1 and not parsed_targets[0].is_file():
            errors.append(f"missing installed SSOT target: {parsed_targets[0]}")
            continue
        matching_kind = next((kind for kind, root in package_roots.items()
                              if parsed_targets == [expected_package_target(name, root).resolve()]), None)
        if matching_kind is None:
            errors.append(
                f"unexpected installed SSOT target: {pointer}; expected "
                + " or ".join(str(expected_package_target(name, root))
                              for root in package_roots.values())
            )
            continue
        if selected_kind is not None and selected_kind != matching_kind:
            errors.append(f"mixed installed package roots: {pointer}")
        selected_kind = matching_kind
    return checked, errors


def build_result(installed_root: Path | None) -> dict[str, object]:
    checked, errors = validate_templates()
    installed_target_kind = None
    if installed_root is not None:
        installed_checked, installed_errors = validate_installed(installed_root)
        checked.extend(installed_checked)
        errors.extend(installed_errors)
        if installed_checked and not installed_errors:
            installed_target_kind = next((kind for kind, root in installed_package_roots().items()
                                          if all(Path(target).is_relative_to(root)
                                                 for target in installed_checked)), None)
    return {
        "ok": not errors,
        "package_root": str(ROOT),
        "installed_root": str(installed_root) if installed_root else None,
        "installed_target_kind": installed_target_kind,
        "checked_targets": checked,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = build_result(args.installed_root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print(f"OK checked_targets={len(result['checked_targets'])}")
    else:
        print("NG")
        for error in result["errors"]:
            print(f"- {error}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
