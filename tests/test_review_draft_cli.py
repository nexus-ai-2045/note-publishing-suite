"""Review draft CLI contract tests."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DRAFT = ROOT / "content/drafts/sample-note-prepublish-fixture.md"


def load_review_draft_module():
    spec = importlib.util.spec_from_file_location(
        "review_draft", ROOT / "scripts" / "review_draft.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_context_card_uses_draft_metadata_and_prepublish_warnings():
    review_draft = load_review_draft_module()
    card = review_draft.build_context_card(FIXTURE_DRAFT)

    assert card["schema"] == "note_review_context_card.v1"
    assert card["article_lane"] == "editor_fixture"
    assert card["source_mode"] == "fixture_only"
    assert card["publication_gate"] == "human_review_required"
    assert card["external_action"] == "none"
    assert card["prepublish"]["overall"] == "warning"
    assert any(issue["code"] == "todo_marker" for issue in card["prepublish"]["issues"])
    assert card["external_actions_performed"] == []
    assert card["publication_actions_performed"] == []


def test_review_draft_contract_blocks_editor_fixture_with_reasons_and_questions():
    review_draft = load_review_draft_module()
    payload = review_draft.review_draft(FIXTURE_DRAFT)

    assert payload["schema"] == "note_review_draft.v1"
    assert payload["verdict"] == "blocked"
    assert "editor_fixture_not_publication_candidate" in payload["reason_codes"]
    assert "fixture_only_source_mode" in payload["reason_codes"]
    assert "publication_gate_human_review_required" in payload["reason_codes"]
    assert "prepublish_warning_todo_marker" in payload["reason_codes"]
    assert payload["confirmation_questions"]
    assert payload["context_card"]["schema"] == "note_review_context_card.v1"
    assert payload["external_actions_performed"] == []
    assert payload["publication_actions_performed"] == []


def test_review_draft_cli_json_contract_and_blocked_exit_code():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/review_draft.py"),
            "review-draft",
            str(FIXTURE_DRAFT),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "blocked"
    assert isinstance(payload["reason_codes"], list)
    assert isinstance(payload["confirmation_questions"], list)
    assert payload["context_card"]["draft"].endswith("sample-note-prepublish-fixture.md")


def test_build_context_card_cli_json_contract():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/review_draft.py"),
            "build-context-card",
            str(FIXTURE_DRAFT),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "note_review_context_card.v1"
    assert payload["prepublish"]["overall"] == "warning"
