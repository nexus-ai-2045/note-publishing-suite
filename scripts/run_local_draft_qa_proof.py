#!/usr/bin/env python3
"""Run one local Note draft through QA and stop before publication."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DRAFT = ROOT / "content/drafts/sample-note-prepublish-fixture.md"
DEFAULT_OUTPUT = ROOT / "data/local_draft_qa_stop_before_publish_evidence.json"


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_json(stdout: str) -> Any:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def run_step(label: str, args: list[str], timeout: float = 240) -> dict[str, Any]:
    step: dict[str, Any] = {
        "label": label,
        "command": "python " + " ".join(args),
        "timeout_seconds": timeout,
        "timed_out": False,
    }
    try:
        result = subprocess.run(
            [sys.executable, *args], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout,
        )
        step.update(exit_code=result.returncode, stdout=result.stdout.strip(), stderr=result.stderr.strip())
    except subprocess.TimeoutExpired as exc:
        def output(value: str | bytes | None) -> str:
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
        step.update(exit_code=124, stdout=output(exc.stdout).strip(), stderr=output(exc.stderr).strip(), timed_out=True)
    except OSError as exc:
        step.update(exit_code=127, stdout="", stderr=str(exc))
    step["parsed_json"] = parse_json(step["stdout"])
    return step


def search_evidence(
    fact: dict[str, Any], *, queries: list[str], endpoint: str, limit: int, dry_run: bool,
) -> dict[str, Any]:
    results = fact.get("search_results", [])
    evidence: dict[str, Any] = {
        "requested_queries": queries, "endpoint": endpoint, "limit": limit,
        "status": "not_requested", "attempt_state": "not_attempted",
        "verification": "unverified", "body_status": "not_fetched", "results": results,
    }
    if not queries:
        return evidence
    if dry_run:
        evidence["status"] = "dry_run"
        return evidence
    valid = (
        isinstance(results, list) and len(results) == len(queries)
        and all(
            isinstance(item, dict) and item.get("query") == query
            and item.get("status") in {"ok", "partial", "no_results", "error", "unavailable"}
            and isinstance(item.get("candidates"), list)
            for query, item in zip(queries, results)
        )
    )
    if not valid:
        evidence.update(status="invalid_report", attempt_state="unknown")
        return evidence
    evidence["attempt_state"] = "attempted"
    statuses = {item["status"] for item in results}
    if statuses & {"error", "unavailable"}:
        evidence["status"] = "error"
    elif "partial" in statuses:
        evidence["status"] = "partial"
    elif statuses == {"no_results"}:
        evidence["status"] = "no_results"
    else:
        evidence["status"] = "candidates_unverified"
    return evidence


def build_evidence(
    *,
    draft: Path,
    preview: Path,
    note_url: str,
    phrases: list[str],
    steps: list[dict[str, Any]],
    search_queries: list[str] | None = None,
    endpoint: str = "http://127.0.0.1:8888",
    limit: int = 5,
    dry_run: bool = False,
) -> dict[str, Any]:
    reports = [step.get("parsed_json") for step in steps]
    pre_publish = reports[1] if isinstance(reports[1], dict) else {}
    fact_check = reports[2] if isinstance(reports[2], dict) else {}
    diff_check = reports[3] if isinstance(reports[3], dict) else {}
    command_failures = [step["label"] for step in steps if step.get("exit_code") != 0]
    count = fact_check.get("finding_count")
    findings = fact_check.get("findings")
    fact_valid = (
        type(count) is int and count >= 0 and isinstance(findings, list)
        and count == len(findings) and all(isinstance(item, dict) for item in findings)
    )
    evidence_errors = [] if fact_valid else ["fact_check_report_invalid"]
    search = search_evidence(
        fact_check, queries=search_queries or [], endpoint=endpoint, limit=limit, dry_run=dry_run,
    )
    if search["status"] == "invalid_report":
        evidence_errors.append("search_report_invalid")
    elif search["status"] == "error":
        evidence_errors.append("source_search_failed")
    pre_publish_overall = pre_publish.get("overall", "unknown")
    fact_finding_count = count if fact_valid else None
    diff_overall = diff_check.get("overall", "unknown")
    external_actions = []
    external_attempts = []
    external_unknown = False
    if search_queries and not dry_run:
        external_attempts.append({"action": "source_search", "state": search["attempt_state"],
                                  "endpoint": endpoint, "queries": search_queries})
        if search["status"] in {"error", "invalid_report"}:
            external_unknown = True
        elif search["attempt_state"] == "attempted":
            external_actions.append({"action": "source_search_attempted", "endpoint": endpoint,
                                     "queries": search_queries})
    if diff_check.get("external_fetch_performed") is True:
        external_actions.append({"action": "note_diff_fetch", "url": note_url})
        external_attempts.append({"action": "note_diff_fetch", "state": "attempted", "url": note_url})
    elif (not dry_run and note_url.strip().lower() not in {"unknown", "none", "-", ""}
          and diff_check.get("external_fetch_performed") is not False
          and diff_check.get("overall") != "skipped"):
        external_unknown = True
        external_attempts.append({"action": "note_diff_fetch", "state": "unknown", "url": note_url})

    stop_causes: list[str] = []
    if command_failures:
        stop_causes.append("qa_command_failed")
    stop_causes.extend(evidence_errors)
    if search["status"] not in {"not_requested", "dry_run"}:
        stop_causes.append("source_search_unverified")
    if pre_publish_overall != "ok":
        stop_causes.append("pre_publish_not_clean")
    pre_publish_issue_codes = {
        str(issue.get("code", ""))
        for issue in pre_publish.get("issues", [])
        if isinstance(issue, dict)
    }
    if pre_publish_issue_codes & {"future_date_guard", "publish_time_recheck", "future_dated_claim", "publish_time_recheck_required"}:
        stop_causes.append("future_date_guard")
    if fact_finding_count:
        stop_causes.append("fact_check_candidates_remain")
    if diff_overall == "skipped":
        stop_causes.append("dry_run_diff_not_performed" if dry_run else "note_url_unknown_diff_not_performed")
    elif diff_overall not in {"ok", "unknown"}:
        stop_causes.append("diff_check_not_clean")
    stop_causes.append("human_review_required")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "proof": "one_local_draft_through_qa_and_stop_before_publish",
        "draft": rel(draft),
        "preview_html": rel(preview),
        "note_url": note_url,
        "phrases": phrases,
        "overall": "failed" if command_failures or evidence_errors else "stopped_before_publish",
        "evidence_errors": evidence_errors,
        "qa_lane": "return_to_draft" if stop_causes else "clean_local_qa",
        "pre_publish_overall": pre_publish_overall,
        "pre_publish_issues": pre_publish.get("issues", []),
        "fact_check_finding_count": fact_finding_count,
        "fact_check_findings": findings if fact_valid else None,
        "fact_check_verification": "unverified",
        "source_search": search,
        "diff_check": diff_check,
        "diff_fetch_method": diff_check.get("fetch_method", "not_performed"),
        "publication_gate": {
            "state": "stopped_before_publish",
            "stop_causes": stop_causes,
            "human_review_required": True,
            "explicit_current_conversation_approval": False,
        },
        "external_actions_performed": None if external_unknown else external_actions,
        "external_actions_confirmed": external_actions,
        "external_action_attempts": external_attempts,
        "external_actions_status": "unknown" if external_unknown else "known",
        "publication_actions_performed": [],
        "commands": steps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run preview, pre-publish, fact-check, and optional diff checks for "
            "one local draft, then record the publication stop line."
        )
    )
    parser.add_argument("draft", nargs="?", type=Path, default=DEFAULT_DRAFT)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--note-url", default="Unknown")
    parser.add_argument("--phrase", action="append", default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--search-query", action="append", default=[], help="出典候補を検索する明示的な検索語")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8888")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true", help="検索と公開ページ取得を実行せずQAを記録")
    parser.add_argument("--step-timeout", type=float, default=240, help="各QAコマンドの制限秒数")
    args = parser.parse_args()
    if not 0 < args.step_timeout <= 600:
        parser.error("制限秒数は0秒超600秒以下です")

    draft = args.draft if args.draft.is_absolute() else ROOT / args.draft
    preview = args.preview or draft.with_suffix(".proof.preview.html")
    preview = preview if preview.is_absolute() else ROOT / preview
    output = args.output if args.output.is_absolute() else ROOT / args.output

    fact_args = ["scripts/note_fact_check.py", "local", rel(draft), "--json",
                 "--endpoint", args.endpoint, "--limit", str(args.limit)]
    for query in args.search_query:
        fact_args.extend(["--search-query", query])
    if args.dry_run:
        fact_args.append("--dry-run")
    steps = [
        run_step("note_preview", ["scripts/note_preview.py", rel(draft), "-o", rel(preview)], args.step_timeout),
        run_step("pre_publish_check", ["scripts/pre_publish_check.py", rel(draft), "--json"], args.step_timeout),
        run_step("note_fact_check", fact_args, args.step_timeout),
    ]
    if args.dry_run:
        steps.append({"label": "note_diff_check", "exit_code": 0,
                      "parsed_json": {"overall": "skipped", "reason": "dry_run", "external_fetch_performed": False}})
    else:
        steps.append(run_step(
            "note_diff_check",
            ["scripts/note_diff_check.py", args.note_url, rel(draft), *args.phrase, "--json"],
            args.step_timeout,
        ))
    evidence = build_evidence(
        draft=draft,
        preview=preview,
        note_url=args.note_url,
        phrases=args.phrase,
        steps=steps,
        search_queries=args.search_query, endpoint=args.endpoint, limit=args.limit, dry_run=args.dry_run,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    else:
        print(f"evidence_json={rel(output)}")
        print(f"overall={evidence['overall']}")
        print("publication_actions_performed=0")
        actions = evidence["external_actions_performed"]
        print(f"external_actions_performed={len(actions) if actions is not None else 'unknown'}")
        print(f"source_search_status={evidence['source_search']['status']}")

    return 1 if evidence["overall"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
