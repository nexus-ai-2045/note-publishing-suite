#!/usr/bin/env python3
"""Guard GitHub repository identity, remote owner, and commit attribution."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_OWNER = "nexus-ai-2045"
EXPECTED_REPO = "note-publishing-suite"
EXPECTED_REPOSITORY = "nexus-ai-2045/note-publishing-suite"
EXPECTED_GIT_NAME = "nexus_ai"
EXPECTED_GIT_EMAIL = "nexus.ai.2045@gmail.com"
ALLOWED_GITHUB_COMMITTER = ("GitHub", "noreply@github.com")
DEFAULT_LOCAL_POLICY = ROOT / "data" / "github_identity_guard_policy.local.json"
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".ps1", ".html"}
SKIP_PATHS = {
    "scripts/github_identity_guard.py",
    "scripts/test_skill_integration.py",
    "data/github_identity_guard_policy.example.json",
}


def load_local_policy(path: Path) -> tuple[set[str], set[str]]:
    if not path.exists():
        return set(), set()
    data = json.loads(path.read_text(encoding="utf-8"))
    terms = {
        str(item).strip()
        for key in ("forbidden_accounts", "forbidden_emails", "forbidden_terms")
        for item in data.get(key, [])
        if str(item).strip()
    }
    allowed_paths = {str(item).replace("\\", "/") for item in data.get("allowed_paths", [])}
    allowed_paths.add(repo_relative(path))
    return terms, allowed_paths


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stdout.strip()


def git_toplevel() -> Path | None:
    top = run_git("rev-parse", "--show-toplevel")
    if not top:
        return None
    return Path(top).resolve()


def is_embedded_copy() -> bool:
    top = git_toplevel()
    return top is None or top != ROOT.resolve()


def add_error(errors: list[dict[str, str]], check: str, message: str) -> None:
    errors.append({"check": check, "message": message})


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def check_repository_env(errors: list[dict[str, str]]) -> None:
    repository = os.environ.get("GITHUB_REPOSITORY")
    if repository and repository != EXPECTED_REPOSITORY:
        add_error(
            errors,
            "github_repository",
            f"GITHUB_REPOSITORY must be {EXPECTED_REPOSITORY}, got {repository}",
        )


def check_remote(errors: list[dict[str, str]], forbidden_terms: set[str]) -> None:
    remotes = run_git("remote", "-v")
    for forbidden in forbidden_terms:
        if forbidden.lower() in remotes.lower():
            add_error(errors, "remote", "remote contains forbidden GitHub account")
    if EXPECTED_REPOSITORY not in remotes:
        add_error(errors, "remote", f"remote must point to {EXPECTED_REPOSITORY}")


def check_head_identity(errors: list[dict[str, str]]) -> None:
    fields = run_git(
        "log",
        "-1",
        "--pretty=format:%an%x00%ae%x00%cn%x00%ce",
    ).split("\x00")
    if len(fields) != 4:
        add_error(errors, "head_commit", "could not read HEAD author and committer")
        return

    author_name, author_email, committer_name, committer_email = fields
    expected_author = {
        "author_name": (author_name, EXPECTED_GIT_NAME),
        "author_email": (author_email, EXPECTED_GIT_EMAIL),
    }
    for label, (actual, wanted) in expected_author.items():
        if actual != wanted:
            add_error(errors, "head_commit", f"{label} must be {wanted}, got {actual}")

    committer_pair = (committer_name, committer_email)
    allowed_committers = {
        (EXPECTED_GIT_NAME, EXPECTED_GIT_EMAIL),
        ALLOWED_GITHUB_COMMITTER,
    }
    if committer_pair not in allowed_committers:
        add_error(
            errors,
            "head_commit",
            "committer must be canonical identity or GitHub merge committer, "
            f"got {committer_name} <{committer_email}>",
        )


def check_local_git_config(errors: list[dict[str, str]]) -> None:
    # Enforce only repository-local identity. Fresh clones inherit user-global
    # config, and that must not make read-only verification fail.
    name = run_git("config", "--local", "--get", "user.name")
    email = run_git("config", "--local", "--get", "user.email")
    if name and name != EXPECTED_GIT_NAME:
        add_error(errors, "git_config", f"user.name must be {EXPECTED_GIT_NAME}, got {name}")
    if email and email != EXPECTED_GIT_EMAIL:
        add_error(
            errors,
            "git_config",
            f"user.email must be {EXPECTED_GIT_EMAIL}, got {email}",
        )


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS:
            files.append(path)
    return files


def check_forbidden_text(
    errors: list[dict[str, str]],
    forbidden_terms: set[str],
    allowed_paths: set[str],
) -> None:
    normalized_terms = {item.lower() for item in forbidden_terms}
    if not normalized_terms:
        return
    for path in iter_text_files():
        rel = repo_relative(path)
        if rel in SKIP_PATHS or rel in allowed_paths:
            continue
        try:
            text = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        for term in normalized_terms:
            if term in text:
                add_error(errors, "text_scan", f"{rel} contains forbidden identity term")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_LOCAL_POLICY,
        help="Optional local-only identity denylist policy JSON.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors: list[dict[str, str]] = []
    forbidden_terms, allowed_paths = load_local_policy(args.policy)
    embedded_copy = is_embedded_copy()
    if not embedded_copy:
        check_repository_env(errors)
        check_remote(errors, forbidden_terms)
        check_head_identity(errors)
        check_local_git_config(errors)
    check_forbidden_text(errors, forbidden_terms, allowed_paths)

    result = {
        "ok": not errors,
        "mode": "embedded_copy_text_scan_only" if embedded_copy else "standalone_repository",
        "expected_repository": EXPECTED_REPOSITORY,
        "expected_git_identity": {
            "name": EXPECTED_GIT_NAME,
            "email": EXPECTED_GIT_EMAIL,
        },
        "local_identity_policy": repo_relative(args.policy),
        "local_identity_policy_loaded": args.policy.exists(),
        "forbidden_identity_term_count": len(forbidden_terms),
        "errors": errors,
        "external_actions_performed": [],
        "publication_actions_performed": [],
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif errors:
        print("NG GitHub identity guard failed")
        for error in errors:
            print(f"- {error['check']}: {error['message']}")
    else:
        print("OK GitHub identity guard passed")
        print("external_actions_performed=0")
        print("publication_actions_performed=0")

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
