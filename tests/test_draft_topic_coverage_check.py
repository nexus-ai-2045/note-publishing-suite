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


def test_info_string_does_not_close_fenced_example() -> None:
    for marker in ("```", "~~~"):
        draft = f"{marker}markdown\n{marker}html\n<!-- topic: a3-income -->\n{marker}\n"
        result = evaluate(ledger(), draft)
        assert result["coverage_complete"] is False
        assert "included topic missing draft marker: a3-income" in result["stop_causes"]


def test_only_valid_fence_close_restores_body_markers() -> None:
    draft = "````markdown\n```\n<!-- topic: fake -->\n~~~~\n````html\n<!-- topic: fake -->\n`````  \t\n<!-- topic: a3-income -->\n"
    result = evaluate(ledger(), draft)
    assert result["coverage_complete"] is True, result
    assert result["marker_count"] == 1


def ledger_v2() -> dict[str, object]:
    data = ledger()
    data["schema_version"] = "note-topic-coverage/v2"
    data["topics"].append({
        "id": "grok-adopted",
        "topic": "Adopted AI framing",
        "source_id": "grok",
        "origin": "ai_suggestion",
        "evidence": "reply 5",
        "disposition": "include",
        "destination": "A3 / middle",
        "author_explanation": "要するに、仕事より収入の方が怖いってこと",
    })
    data["intent_readbacks"] = [
        {"stage": "start", "ai_summary": "収入の不安を軸に書く", "author_reply": "そう", "confirmed": True},
        {"stage": "transfer", "ai_summary": "収入の不安を軸に書いた", "author_reply": "OK", "confirmed": True},
    ]
    return data


V2_DRAFT = "<!-- topic: a3-income -->\n収入。\n<!-- topic: grok-adopted -->\n枠組み。\n"


def test_v2_passes_with_explanation_and_both_readbacks() -> None:
    result = evaluate(ledger_v2(), V2_DRAFT)
    assert result["ok"] is True
    assert result["author_checks"] == "required"
    assert result["confirmed_readback_stages"] == ["start", "transfer"]


def test_v2_stops_adopted_ai_suggestion_without_author_explanation() -> None:
    data = ledger_v2()
    del data["topics"][2]["author_explanation"]
    result = evaluate(data, V2_DRAFT)
    assert result["ok"] is False
    assert result["unexplained_ai_suggestions"] == ["grok-adopted"]


def test_v2_stops_when_transfer_readback_missing_or_unconfirmed() -> None:
    data = ledger_v2()
    data["intent_readbacks"][1]["confirmed"] = False
    result = evaluate(data, V2_DRAFT)
    assert result["ok"] is False
    assert "intent readback missing for stage: transfer" in result["stop_causes"]


def test_v2_accepts_ai_connective_origin_but_v1_rejects_it() -> None:
    data = ledger_v2()
    data["topics"][0]["origin"] = "ai_connective"
    assert evaluate(data, V2_DRAFT)["ok"] is True
    v1 = ledger()
    v1["topics"][0]["origin"] = "ai_connective"
    assert evaluate(v1, "<!-- topic: a3-income -->\n")["ok"] is False


def test_v1_ledger_is_unchanged_by_author_checks() -> None:
    result = evaluate(ledger(), "<!-- topic: a3-income -->\n収入。\n")
    assert result["ok"] is True
    assert result["author_checks"] == "not_requested"
