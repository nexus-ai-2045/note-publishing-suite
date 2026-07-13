#!/usr/bin/env python3
"""Fail closed when Claude Code pointer skills reference missing package SSOT files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_ROOT = ROOT / "adapters" / "claude-code"
PACKAGE_TARGET_RE = re.compile(r"\{\{PACKAGE_ROOT\}\}(/[^\s`]*SKILL\.md)")
INSTALLED_TARGET_RE = re.compile(r"(/[^\s`]*SKILL\.md)")


def adapter_names() -> list[str]:
    return sorted(path.parent.name for path in ADAPTER_ROOT.glob("*/SKILL.md"))


def validate_templates() -> tuple[list[str], list[str]]:
    checked: list[str] = []
    errors: list[str] = []
    for template in sorted(ADAPTER_ROOT.glob("*/SKILL.md")):
        text = template.read_text(encoding="utf-8")
        targets = PACKAGE_TARGET_RE.findall(text)
        if not targets:
            errors.append(f"{template.relative_to(ROOT)}: package SSOT pointer not found")
            continue
        for suffix in targets:
            target = ROOT / suffix.lstrip("/")
            checked.append(str(target))
            if not target.is_file():
                errors.append(f"missing package SSOT target: {target}")
    return checked, errors


def validate_installed(installed_root: Path) -> tuple[list[str], list[str]]:
    checked: list[str] = []
    errors: list[str] = []
    for name in adapter_names():
        pointer = installed_root / name / "SKILL.md"
        if not pointer.is_file():
            errors.append(f"missing installed pointer: {pointer}")
            continue
        targets = INSTALLED_TARGET_RE.findall(pointer.read_text(encoding="utf-8"))
        if not targets:
            errors.append(f"installed pointer has no absolute SSOT target: {pointer}")
            continue
        for raw_target in targets:
            target = Path(raw_target)
            checked.append(str(target))
            if not target.is_file():
                errors.append(f"missing installed SSOT target: {target}")
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
