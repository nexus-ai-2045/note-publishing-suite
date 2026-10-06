"""Focused checks for conversation-topic coverage in an article draft."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.draft_topic_coverage_check import evaluate


ROOT = Path(__file__).resolve().parents[1]


def ledger() -> dict[str, object]:
    return {
        "schema_version": "note-topic-coverage/v1",
        "sources": [
            {
                "id": "conversation",
                "kind": "codex_conversation",
                "uri": "conversation://current",
                "capture_status": "complete",
            },
            {
                "id": "grok",
                "kind": "grok_conversation",
                "uri": "https://grok.com/c/example",
                "capture_status": "complete",
            },
        ],
        "topics": [
            {
                "id": "a3-income",
                "topic": "Income loss is one fear of job loss",
                "source_id": "conversation",
                "origin": "user_speech",
                "evidence": "turn 42",
                "disposition": "include",
                "destination": "A3 / opening",
            },
            {
                "id": "grok-model",
                "topic": "One possible distribution model",
                "source_id": "grok",
                "origin": "ai_suggestion",
                "evidence": "reply 3",
                "disposition": "defer",
                "destination": "A4",
                "reason": "Outside A3 scope",
            },
        ],
    }


def test_included_topic_marker_and_deferred_reason_pass() -> None:
    draft = "---\ntitle: Sample\n---\n\n<!-- topic: a3-income -->\n収入がなくなる怖さ。\n"
    result = evaluate(ledger(), draft)
    assert result["ok"] is True
    assert result["topic_count"] == 2
    assert result["marker_count"] == 1
    assert result["disposition_counts"] == {"defer": 1, "include": 1}


def test_missing_marker_and_reason_are_reported() -> None:
    data = ledger()
    data["topics"][1].pop("reason")
    result = evaluate(data, "# Article\n")
    assert result["ok"] is False
    assert "included topic missing draft marker: a3-income" in result["stop_causes"]
    assert "topics[1]: reason is required" in result["stop_causes"]


def test_partial_source_prevents_false_complete_claim() -> None:
    data = ledger()
    data["sources"][1]["capture_status"] = "partial"
    result = evaluate(data, "<!-- topic: a3-income -->\n")
    assert result["ok"] is False
    assert result["incomplete_sources"] == ["grok"]
    assert "source capture incomplete: grok" in result["stop_causes"]


def test_unknown_or_nonincluded_marker_is_reported() -> None:
    draft = "<!-- topic: a3-income -->\n<!-- topic: grok-model -->\n<!-- topic: unknown -->\n"
    result = evaluate(ledger(), draft)
    assert "non-included topic marked in draft: grok-model" in result["stop_causes"]
    assert "unknown draft marker: unknown" in result["stop_causes"]


def test_code_fence_example_does_not_count_as_article_marker() -> None:
    draft = "```md\n<!-- topic: a3-income -->\n```\n"
    result = evaluate(ledger(), draft)
    assert "included topic missing draft marker: a3-income" in result["stop_causes"]


def test_cli_json_contract(tmp_path: Path) -> None:
    ledger_path = tmp_path / "topics.json"
    draft_path = tmp_path / "draft.md"
    ledger_path.write_text(json.dumps(ledger()), encoding="utf-8")
    draft_path.write_text("<!-- topic: a3-income -->\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/draft_topic_coverage_check.py"),
         str(ledger_path), str(draft_path), "--json"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["external_actions_performed"] == []
