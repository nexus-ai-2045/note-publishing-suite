"""QA入口の検索証跡と無通信の既定を検証する。"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_local_draft_qa_proof.py"
SPEC = importlib.util.spec_from_file_location("local_qa_search", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
qa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qa)


def steps(fact=None, exit_code=0):
    return [
        {"label": "preview", "exit_code": 0, "parsed_json": None},
        {"label": "pre_publish", "exit_code": 0, "parsed_json": {"overall": "ok"}},
        {"label": "fact", "exit_code": exit_code, "parsed_json": fact},
        {"label": "diff", "exit_code": 0, "parsed_json": {"overall": "skipped"}},
    ]


def evidence(fact=None, **kwargs):
    return qa.build_evidence(
        draft=Path("draft.md"), preview=Path("preview.html"), note_url="Unknown",
        phrases=[], steps=steps(fact), **kwargs,
    )


def report(status):
    return {"finding_count": 0, "findings": [], "search_results": [
        {"query": "explicit query", "status": status, "verification": "unverified",
         "candidates": [{"url": "https://example.com", "body_status": "not_fetched"}]
         if status in {"ok", "partial"} else [], "unresponsive_engines": []}
    ]}


@pytest.mark.parametrize("status,expected", [
    ("ok", "candidates_unverified"), ("partial", "partial"), ("no_results", "no_results"),
    ("error", "error"), ("unavailable", "error"),
])
def test_search_outcomes_are_evidence_not_verification(status, expected):
    result = evidence(report(status), search_queries=["explicit query"])
    assert result["source_search"]["status"] == expected
    assert result["source_search"]["results"] == report(status)["search_results"]
    assert result["source_search"]["attempt_state"] == "attempted"
    assert result["source_search"]["verification"] == "unverified"
    assert result["fact_check_verification"] == "unverified"
    if status in {"error", "unavailable"}:
        assert result["external_actions_performed"] is None
    else:
        assert result["external_actions_performed"][0]["action"] == "source_search_attempted"
    assert result["publication_actions_performed"] == []
    assert result["publication_gate"]["human_review_required"] is True


@pytest.mark.parametrize("fact", [None, [], "bad", {}, {"finding_count": "bad"},
                                      {"finding_count": 0, "findings": [1]}])
def test_missing_or_invalid_fact_report_is_not_zero_findings(fact):
    result = evidence(fact, search_queries=["explicit query"])
    assert result["overall"] == "failed"
    assert result["fact_check_finding_count"] is None
    assert result["source_search"]["status"] == "invalid_report"
    assert result["source_search"]["attempt_state"] == "unknown"


def test_default_has_no_search_or_external_actions():
    result = evidence({"finding_count": 0, "findings": []})
    assert result["source_search"]["status"] == "not_requested"
    assert result["source_search"]["attempt_state"] == "not_attempted"
    assert result["external_actions_performed"] == []


def test_cli_routes_explicit_search_options_and_dry_run(monkeypatch, tmp_path, capsys):
    output = tmp_path / "evidence.json"
    calls = []

    def run(label, args, timeout):
        calls.append((label, args, timeout))
        payload = {"finding_count": 0, "findings": []} if label == "note_fact_check" else {"overall": "ok"}
        return {"label": label, "exit_code": 0, "parsed_json": payload}

    monkeypatch.setattr(qa, "run_step", run)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--output", str(output), "--json",
        "--search-query", "first", "--search-query", "second", "--endpoint", "http://127.0.0.1:9999",
        "--limit", "2", "--step-timeout", "5", "--dry-run", "--note-url", "https://example.com"])
    assert qa.main() == 0
    result = json.loads(capsys.readouterr().out)
    command = calls[2][1]
    assert command[-5:] == ["--search-query", "first", "--search-query", "second", "--dry-run"]
    assert command[command.index("--endpoint") + 1] == "http://127.0.0.1:9999"
    assert command[command.index("--limit") + 1] == "2"
    assert all(timeout == 5 for _, _, timeout in calls)
    assert len(calls) == 3
    assert result["source_search"]["status"] == "dry_run"
    assert result["external_actions_performed"] == []
    assert json.loads(output.read_text()) == result


@pytest.mark.parametrize("failure,exit_code", [
    (subprocess.TimeoutExpired("command", 1, output=b'{"partial":', stderr=b"partial stderr"), 124),
    (OSError("cannot start"), 127),
])
def test_failed_commands_preserve_evidence(monkeypatch, failure, exit_code):
    runner = Mock(side_effect=failure)
    monkeypatch.setattr(qa.subprocess, "run", runner)
    result = qa.run_step("fact", ["scripts/note_fact_check.py"], timeout=1)
    assert result["exit_code"] == exit_code
    assert result["parsed_json"] is None
    assert runner.call_args.kwargs["timeout"] == 1
    if exit_code == 124:
        assert result["timed_out"] is True
        assert result["stdout"] == '{"partial":'
        assert result["stderr"] == "partial stderr"
    all_steps = steps()
    all_steps[2] = result
    proof = qa.build_evidence(draft=Path("draft.md"), preview=Path("preview.html"),
                             note_url="Unknown", phrases=[], steps=all_steps,
                             search_queries=["explicit query"])
    assert proof["overall"] == "failed"
    assert proof["source_search"]["attempt_state"] == "unknown"
    assert "qa_command_failed" in proof["publication_gate"]["stop_causes"]


def test_invalid_json_successful_process_fails_evidence(monkeypatch):
    monkeypatch.setattr(qa.subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 0, "not json", "")))
    step = qa.run_step("fact", ["fact.py"])
    assert step["parsed_json"] is None
    assert evidence(step["parsed_json"])["overall"] == "failed"


def test_error_exit_retains_search_results(monkeypatch):
    payload = report("error")
    monkeypatch.setattr(qa.subprocess, "run", Mock(return_value=subprocess.CompletedProcess(
        [], 2, json.dumps(payload), "engine unavailable")))
    step = qa.run_step("fact", ["fact.py"])
    all_steps = steps()
    all_steps[2] = step
    proof = qa.build_evidence(draft=Path("draft.md"), preview=Path("preview.html"),
                             note_url="Unknown", phrases=[], steps=all_steps,
                             search_queries=["explicit query"])
    assert proof["overall"] == "failed"
    assert proof["source_search"]["status"] == "error"
    assert proof["source_search"]["results"] == payload["search_results"]
    assert proof["source_search"]["attempt_state"] == "attempted"


def test_default_cli_does_not_request_network(monkeypatch, tmp_path, capsys):
    calls = []

    def run(label, args, timeout):
        calls.append((label, args))
        payload = {"finding_count": 0, "findings": []} if label == "note_fact_check" else {"overall": "skipped"}
        return {"label": label, "exit_code": 0, "parsed_json": payload}

    monkeypatch.setattr(qa, "run_step", run)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--output", str(tmp_path / "proof.json"), "--json"])
    assert qa.main() == 0
    assert "--search-query" not in calls[2][1]
    assert calls[3][1][1] == "Unknown"
    assert json.loads(capsys.readouterr().out)["external_actions_performed"] == []


@pytest.mark.parametrize("failure_code", [1, 124])
def test_diff_failure_does_not_claim_zero_external_actions(failure_code):
    all_steps = steps({"finding_count": 0, "findings": []})
    all_steps[3] = {"label": "diff", "exit_code": failure_code, "parsed_json": None,
                    "stderr": "HTTP 403" if failure_code == 1 else "timeout"}
    result = qa.build_evidence(draft=Path("draft.md"), preview=Path("preview.html"),
                              note_url="https://note.com/example/n/n123", phrases=[], steps=all_steps)
    assert result["overall"] == "failed"
    assert result["external_actions_performed"] is None
    assert result["external_actions_status"] == "unknown"
    assert result["external_action_attempts"][0]["state"] == "unknown"


def test_search_timeout_does_not_claim_zero_external_actions():
    all_steps = steps()
    all_steps[2]["exit_code"] = 124
    result = qa.build_evidence(draft=Path("draft.md"), preview=Path("preview.html"),
                              note_url="Unknown", phrases=[], steps=all_steps,
                              search_queries=["explicit query"])
    assert result["external_actions_performed"] is None
    assert result["external_actions_status"] == "unknown"
    assert result["source_search"]["attempt_state"] == "unknown"


@pytest.mark.parametrize("code", ["future_date_guard", "publish_time_recheck",
                                  "future_dated_claim", "publish_time_recheck_required"])
def test_both_upstream_and_consumer_date_guards_are_retained(code):
    all_steps = steps({"finding_count": 0, "findings": []})
    all_steps[1]["parsed_json"] = {"overall": "warning", "issues": [{"code": code}]}
    result = qa.build_evidence(draft=Path("draft.md"), preview=Path("preview.html"),
                              note_url="Unknown", phrases=[], steps=all_steps)
    assert "future_date_guard" in result["publication_gate"]["stop_causes"]
    assert result["diff_fetch_method"] == "not_performed"


def test_cli_forwards_production_review_inputs(monkeypatch, tmp_path):
    calls = []
    def run(label, args, timeout):
        calls.append((label, args))
        payload = {"finding_count": 0, "findings": []} if label == "note_fact_check" else {"overall": "ok"}
        return {"label": label, "exit_code": 0, "parsed_json": payload}
    options = ["--settings", str(tmp_path / "settings.json"), "--article-id", "article",
               "--conversation-id", "current", "--authorship-evidence", str(tmp_path / "authorship.json"),
               "--prepublish-review-receipt", str(tmp_path / "review.json")]
    monkeypatch.setattr(qa, "run_step", run)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--output", str(tmp_path / "out.json"), "--dry-run", *options])
    assert qa.main() == 0
    command = dict(calls)["pre_publish_check"]
    for i in range(0, len(options), 2):
        assert command[command.index(options[i]) + 1] == options[i + 1]
