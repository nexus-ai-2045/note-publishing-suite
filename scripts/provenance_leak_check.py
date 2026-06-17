#!/usr/bin/env python3
"""Check draft/package text for provenance leaks before PR or publication."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCAL_POLICY = ROOT / "data" / "provenance_leak_policy.local.json"
EXAMPLE_POLICY = ROOT / "data" / "provenance_leak_policy.example.json"

TEXT_EXTENSIONS = {
    ".md",
    ".markdown",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".ps1",
    ".html",
}

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
}

GENERIC_RULES = [
    {
        "id": "windows_user_path",
        "pattern": r"C:\\Users\\[^\\\s\"'<>]+",
        "kind": "regex",
        "reason": "Windows local user path should not appear in public package text.",
    },
    {
        "id": "posix_user_path",
        "pattern": r"/Users/[A-Za-z0-9._-]+",
        "kind": "regex",
        "reason": "macOS local user path should not appear in public package text.",
    },
    {
        "id": "github_pat",
        "pattern": r"github_pat_[A-Za-z0-9_]{20,}",
        "kind": "regex",
        "reason": "GitHub fine-grained token-like value.",
    },
    {
        "id": "github_classic_token",
        "pattern": r"ghp_[A-Za-z0-9_]{20,}",
        "kind": "regex",
        "reason": "GitHub token-like value.",
    },
    {
        "id": "openai_key",
        "pattern": r"sk-[A-Za-z0-9_-]{20,}",
        "kind": "regex",
        "reason": "OpenAI key-like value.",
    },
    {
        "id": "runtime_memory_label",
        "pattern": r"\bruntime_memory\b",
        "kind": "regex",
        "reason": "Runtime memory labels should not become article provenance.",
    },
    {
        "id": "git_prompt_artifact",
        "pattern": r"\b(GIT_TERMINAL_PROMPT|askpass|index\.lock|mergeStateStatus)\b",
        "kind": "regex",
        "reason": "Git/auth operational artifacts should not enter article/package provenance.",
    },
]


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: str
    kind: str
    reason: str
    source: str


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def load_policy(path: Path) -> tuple[list[Rule], set[str]]:
    if not path.exists():
        return [], set()
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = []
    for item in data.get("denylist", []):
        pattern = str(item.get("pattern") or "")
        if not pattern:
            continue
        rules.append(
            Rule(
                id=str(item.get("id") or "local_denylist"),
                pattern=pattern,
                kind=str(item.get("kind") or "literal"),
                reason=str(item.get("reason") or "Local provenance denylist match."),
                source=repo_relative(path),
            )
        )
    allowed_paths = {str(item).replace("\\", "/") for item in data.get("allowed_paths", [])}
    return rules, allowed_paths


def default_rules() -> list[Rule]:
    return [
        Rule(
            id=item["id"],
            pattern=item["pattern"],
            kind=item["kind"],
            reason=item["reason"],
            source="builtin",
        )
        for item in GENERIC_RULES
    ]


def iter_text_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            for child in path.rglob("*"):
                if not child.is_file():
                    continue
                if any(part in SKIP_DIRS for part in child.parts):
                    continue
                if child.suffix.lower() in TEXT_EXTENSIONS:
                    yield child
        elif path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            yield path


def git_changed_files() -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not names:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [ROOT / name for name in names]


def match_rule(text: str, rule: Rule) -> bool:
    if rule.kind == "regex":
        return re.search(rule.pattern, text) is not None
    return rule.pattern in text


def check_files(files: list[Path], rules: list[Rule], allowed_paths: set[str]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in sorted(set(files)):
        rel = repo_relative(path)
        if rel in allowed_paths:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for rule in rules:
            if match_rule(text, rule):
                findings.append(
                    {
                        "path": rel,
                        "rule_id": rule.id,
                        "reason": rule.reason,
                        "source": rule.source,
                    }
                )
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=["all", "changed"],
        default="all",
        help="Scan the full package or only git changed files.",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_LOCAL_POLICY,
        help="Optional local denylist policy JSON.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    local_rules, local_allowed = load_policy(args.policy)
    example_rules, example_allowed = load_policy(EXAMPLE_POLICY)
    rules = default_rules() + local_rules
    allowed_paths = set(local_allowed) | set(example_allowed) | {
        "data/provenance_leak_policy.example.json",
        "scripts/provenance_leak_check.py",
    }

    roots = [ROOT] if args.scope == "all" else git_changed_files()
    files = list(iter_text_files(roots))
    findings = check_files(files, rules, allowed_paths)
    result = {
        "ok": not findings,
        "scope": args.scope,
        "checked_files": len(files),
        "policy_loaded": args.policy.exists(),
        "example_policy_loaded": EXAMPLE_POLICY.exists(),
        "findings": findings,
        "external_actions_performed": [],
        "publication_actions_performed": [],
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif findings:
        print("NG provenance leak check failed")
        for finding in findings:
            print(f"- {finding['path']}: {finding['rule_id']} ({finding['reason']})")
    else:
        print("OK provenance leak check passed")
        print(f"checked_files={len(files)}")
        print(f"local_policy_loaded={str(args.policy.exists()).lower()}")
        print("external_actions_performed=0")
        print("publication_actions_performed=0")

    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
