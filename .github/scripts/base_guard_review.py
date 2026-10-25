#!/usr/bin/env python3
"""固定した上流の判定を分類し、GitHub の人間レビュー設定を読取り検証する。"""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request

ENVIRONMENT = "ci-protected-change-review"
SCHEMA = "repo-preflight.base-guard/v2"


class ReviewError(ValueError):
    """公開ログへ出してよい固定メッセージだけを持つ。"""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReviewError("duplicate_json_key")
        result[key] = value
    return result


def read_json(raw):
    try:
        return json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ReviewError("invalid_json") from exc


def classify(report, returncode):
    """人間に渡せるのは上流の完全な protected-only blocked 判定だけ。"""
    if (not isinstance(report, dict)
            or set(report) != {"schema", "status", "callers", "findings"}
            or report["schema"] != SCHEMA
            or type(report["callers"]) is not int or report["callers"] < 1
            or not isinstance(report["findings"], list)):
        raise ReviewError("invalid_guard_report")
    findings = report["findings"]
    if returncode == 0 and report["status"] == "pass" and not findings:
        return False
    if returncode != 1 or report["status"] != "blocked" or not findings:
        raise ReviewError("inconsistent_guard_report")
    paths = set()
    for finding in findings:
        if (not isinstance(finding, dict)
                or set(finding) != {"kind", "file", "job", "side"}
                or finding["kind"] != "protected_path_changed"
                or finding["side"] != "head" or finding["job"] != ""
                or not isinstance(finding["file"], str) or not finding["file"]
                or "\x00" in finding["file"] or finding["file"] in paths):
            raise ReviewError("guard_failure_not_reviewable")
        paths.add(finding["file"])
    return True


def validate_environment(policy, owner_id):
    if (not isinstance(policy, dict) or policy.get("name") != ENVIRONMENT
            or type(owner_id) is not int or owner_id <= 0):
        raise ReviewError("invalid_environment")
    if policy.get("can_admins_bypass") is not False:
        raise ReviewError("environment_admin_bypass_not_disabled")
    branch = policy.get("deployment_branch_policy")
    if (not isinstance(branch, dict) or branch.get("protected_branches") is not True
            or branch.get("custom_branch_policies") is not False):
        raise ReviewError("invalid_environment_branch_policy")
    rules = policy.get("protection_rules")
    if not isinstance(rules, list) or not all(isinstance(rule, dict) for rule in rules):
        raise ReviewError("invalid_environment_rules")
    required = [rule for rule in rules if rule.get("type") == "required_reviewers"]
    if len(required) != 1 or required[0].get("prevent_self_review") is not False:
        raise ReviewError("invalid_environment_review_policy")
    reviewers = required[0].get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) != 1:
        raise ReviewError("invalid_environment_reviewers")
    reviewer = reviewers[0]
    if not isinstance(reviewer, dict) or reviewer.get("type") != "User":
        raise ReviewError("invalid_environment_reviewer")
    identity = reviewer.get("reviewer")
    if (not isinstance(identity, dict) or identity.get("type") != "User"
            or type(identity.get("id")) is not int or identity["id"] != owner_id):
        raise ReviewError("invalid_environment_owner")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReviewError("environment_api_redirect")


def fetch_environment(repository, token):
    # この GitHub.com package の固定ホスト。入力で credential の送信先を変えない。
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", repository):
        raise ReviewError("invalid_repository")
    if not token or "\n" in token or "\r" in token:
        raise ReviewError("missing_api_token")
    url = f"https://api.github.com/repos/{repository}/environments/{ENVIRONMENT}"
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=30) as response:
            if response.status != 200:
                raise ReviewError("environment_api_status")
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ReviewError("environment_api_too_large")
            return read_json(raw)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        # 例外本文や response は認証値・外部入力を含み得るため表示しない。
        raise ReviewError("environment_api_failed") from exc


def inspect(args):
    for value in (args.base, args.head):
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise ReviewError("invalid_commit")
    if not re.fullmatch(r"[1-9][0-9]*", args.pr):
        raise ReviewError("invalid_pr")
    if not re.fullmatch(r"[1-9][0-9]*", args.owner_id):
        raise ReviewError("invalid_owner_id")
    if args.owner_type != "User":
        raise ReviewError("unsupported_owner_type")
    # credential を上流 subprocess へ渡さない。上流は固定 checkout のみ実行する。
    token = os.environ.pop("REVIEW_API_TOKEN", "")
    result = subprocess.run([
        sys.executable, "-I", str(Path(args.tool) / "scripts/base_guard.py"),
        "--repo", args.repo, "--base-ref", args.base, "--head-ref", args.head,
        "--trusted-tool", args.tool, "--json",
    ], capture_output=True, timeout=120, check=False)
    required = classify(read_json(result.stdout), result.returncode)
    if required:
        validate_environment(fetch_environment(args.repository, token), int(args.owner_id))
    summary = ["## base-guard の検査", f"PR: {args.pr}",
               f"base: {args.base}", f"head: {args.head}",
               "保護パス変更: GitHub Environment の本人確認が必要" if required else "上流検査: pass"]
    # HTML entity と JSON escape の両方で、改行・Markdown・workflow command をデータ化。
    summary.extend("<pre>" + html.escape(json.dumps(item["file"], ensure_ascii=True)) + "</pre>"
                   for item in read_json(result.stdout)["findings"])
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
        stream.write("\n\n".join(summary) + "\n")
    # 出力は全検査が通った後の固定 boolean のみ。
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
        stream.write(f"review_required={str(required).lower()}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "tool", "base", "head", "pr", "repository", "owner-id", "owner-type"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args()
    try:
        inspect(args)
    except (ReviewError, OSError, subprocess.SubprocessError, KeyError):
        print("base-guard: 検査または人間レビュー設定を確認できないため停止します", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
