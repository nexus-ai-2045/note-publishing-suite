"""コミッター名義の判定（メールの完全一致＋メールごとの表示名 allowlist）の試験。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_EMAIL = "273569186+nexus-ai-2045@users.noreply.github.com"
GITHUB_EMAIL = "noreply@github.com"
# 別のアカウントの noreply と、個人メールの形（どちらも架空）。
# 別アカウントの noreply は、架空の番号と名前を GitHub の noreply の形に当てはめて作る。
NOREPLY_DOMAIN = "users.noreply.github.com"
OTHER_ACCOUNT_NOREPLY = "{}+{}@{}".format("100000001", "fixture-other-account", NOREPLY_DOMAIN)
PERSONAL_MAIL_SHAPE = "fixture-person@example.invalid"


def load_guard():
    spec = importlib.util.spec_from_file_location(
        "github_identity_guard_committer_under_test",
        ROOT / "scripts" / "github_identity_guard.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def head_errors(guard, committer_name: str, committer_email: str) -> list[dict[str, str]]:
    fields = ["nexus-ai-2045", CANONICAL_EMAIL, committer_name, committer_email]
    original = guard.run_git
    guard.run_git = lambda *args: "\x00".join(fields)
    try:
        errors: list[dict[str, str]] = []
        guard.check_head_identity(errors)
        return errors
    finally:
        guard.run_git = original


@pytest.mark.parametrize(
    ("name", "email"),
    [
        ("nexus_ai", CANONICAL_EMAIL),  # GitHub のリベースマージで付くコミッター
        ("nexus-ai-2045", CANONICAL_EMAIL),
        ("GitHub", GITHUB_EMAIL),
    ],
)
def test_allowed_committers_pass(name: str, email: str):
    guard = load_guard()
    assert guard.committer_allowed(name, email) is True
    assert head_errors(guard, name, email) == []


@pytest.mark.parametrize(
    ("name", "email"),
    [
        # 別のアカウントの noreply は、表示名が許可の名前でも止まる
        ("nexus_ai", OTHER_ACCOUNT_NOREPLY),
        ("nexus-ai-2045", OTHER_ACCOUNT_NOREPLY),
        ("GitHub", OTHER_ACCOUNT_NOREPLY),
        # 個人メールの形は止まる
        ("nexus_ai", PERSONAL_MAIL_SHAPE),
        ("nexus-ai-2045", PERSONAL_MAIL_SHAPE),
        # 名前とメールの組み合わせ違いは止まる（名前だけ・メールだけでは通らない）
        ("GitHub", CANONICAL_EMAIL),
        ("nexus_ai", GITHUB_EMAIL),
        ("fixture-other-name", CANONICAL_EMAIL),
        # 完全一致なので、大文字小文字や空白の違いも止まる
        ("NEXUS_AI", CANONICAL_EMAIL),
        ("nexus_ai ", CANONICAL_EMAIL),
        ("nexus_ai", CANONICAL_EMAIL.upper()),
        ("nexus_ai", ""),
        ("", CANONICAL_EMAIL),
    ],
)
def test_other_committers_are_blocked(name: str, email: str):
    guard = load_guard()
    assert guard.committer_allowed(name, email) is False
    errors = head_errors(guard, name, email)
    assert [e["check"] for e in errors] == ["head_commit"]
    assert "committer must be canonical identity or GitHub merge committer" in errors[0]["message"]


def test_allowlist_contains_only_two_emails():
    guard = load_guard()
    assert set(guard.ALLOWED_COMMITTER_NAMES_BY_EMAIL) == {CANONICAL_EMAIL, GITHUB_EMAIL}
    assert guard.ALLOWED_COMMITTER_NAMES_BY_EMAIL[CANONICAL_EMAIL] == {"nexus-ai-2045", "nexus_ai"}
    assert guard.ALLOWED_COMMITTER_NAMES_BY_EMAIL[GITHUB_EMAIL] == {"GitHub"}


def test_author_check_is_unchanged():
    guard = load_guard()
    original = guard.run_git
    guard.run_git = lambda *args: "\x00".join(["nexus_ai", CANONICAL_EMAIL, "GitHub", GITHUB_EMAIL])
    try:
        errors: list[dict[str, str]] = []
        guard.check_head_identity(errors)
    finally:
        guard.run_git = original
    assert errors and errors[0]["message"].startswith("author_name must be nexus-ai-2045")
