#!/usr/bin/env python3
"""Fail closed when Claude Code pointer skills reference missing package SSOT files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_ROOT = ROOT / "adapters" / "claude-code"
PACKAGE_TARGET_RE = re.compile(r"\{\{PACKAGE_ROOT\}\}(/[^`\r\n]*SKILL\.md)")
INSTALLED_TARGET_RE = re.compile(r"(/[^`\r\n]*SKILL\.md)")


def adapter_names() -> list[str]:
    return sorted(path.parent.name for path in ADAPTER_ROOT.glob("*/SKILL.md"))


def expected_package_target(name: str) -> Path:
    if name == "note-publishing-suite":
        return ROOT / "SKILL.md"
    return ROOT / "skills" / name / "SKILL.md"


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
    for name in adapter_names():
        pointer = installed_root / name / "SKILL.md"
        expected = expected_package_target(name)
        if pointer.parent.is_symlink():
            errors.append(f"installed pointer directory must not be a symlink: {pointer.parent}")
            continue
        if pointer.is_symlink():
            errors.append(f"installed pointer must not be a symlink: {pointer}")
            continue
        if not pointer.is_file():
            errors.append(f"missing installed pointer: {pointer}")
            continue
        targets = INSTALLED_TARGET_RE.findall(pointer.read_text(encoding="utf-8"))
        if not targets:
            errors.append(f"installed pointer has no absolute SSOT target: {pointer}")
            continue
        parsed_targets = [Path(raw_target) for raw_target in targets]
        checked.extend(str(target) for target in parsed_targets)
        if len(parsed_targets) == 1 and not parsed_targets[0].is_file():
            errors.append(f"missing installed SSOT target: {parsed_targets[0]}")
            continue
        if parsed_targets != [expected]:
            errors.append(
                f"unexpected installed SSOT target: {pointer}; expected {expected}"
            )
            continue
    return checked, errors


def build_result(installed_root: Path | None) -> dict[str, object]:
    checked, errors = validate_templates()
    if installed_root is not None:
        installed_checked, installed_errors = validate_installed(installed_root)
        checked.extend(installed_checked)
        errors.extend(installed_errors)
    return {
        "ok": not errors,
        "package_root": str(ROOT),
        "installed_root": str(installed_root) if installed_root else None,
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
