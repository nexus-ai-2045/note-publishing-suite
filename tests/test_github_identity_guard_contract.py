"""公開owner/loginと採用済みGit author名の責務を分けて検証する。"""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "github_identity_guard_contract",
    Path(__file__).resolve().parents[1] / "scripts" / "github_identity_guard.py",
)
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


@pytest.mark.parametrize("name,ok", [("nexus_ai", True), ("nexus-ai-2045", False)])
def test_local_name_uses_author_policy_without_changing_owner_or_email(monkeypatch, name, ok):
    values = {"user.name": name, "user.email": GUARD.EXPECTED_GIT_EMAIL}
    monkeypatch.setattr(GUARD, "run_git", lambda *args: values[args[-1]])
    errors = []
    GUARD.check_local_git_config(errors)
    assert (not errors) is ok
    assert GUARD.EXPECTED_OWNER == "nexus-ai-2045"
    assert GUARD.EXPECTED_REPOSITORY == "nexus-ai-2045/note-publishing-suite"


@pytest.mark.parametrize("wrong_field", [None, "author_name", "author_email", "committer_name", "committer_email"])
def test_head_identity_keeps_exact_author_and_committer_binding(monkeypatch, wrong_field):
    fields = {"author_name": GUARD.EXPECTED_GIT_NAME,
              "author_email": GUARD.EXPECTED_GIT_EMAIL,
              "committer_name": GUARD.EXPECTED_GIT_NAME,
              "committer_email": GUARD.EXPECTED_GIT_EMAIL}
    if wrong_field:
        fields[wrong_field] = "unexpected-fixture-value"
    monkeypatch.setattr(GUARD, "run_git", lambda *args: "\0".join(fields.values()))
    errors = []
    GUARD.check_head_identity(errors)
    assert (not errors) is (wrong_field is None)
