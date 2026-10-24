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


def run_step(label: str, args: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "label": label,
        "command": "python " + " ".join(args),
        "exit_code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "parsed_json": parse_json(result.stdout),
    }


def build_evidence(
    *,
    draft: Path,
    preview: Path,
    note_url: str,
    phrases: list[str],
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    pre_publish = steps[1].get("parsed_json") or {}
    fact_check = steps[2].get("parsed_json") or {}
    diff_check = steps[3].get("parsed_json") or {}
    command_failures = [
        step["label"] for step in steps if int(step.get("exit_code", 1)) != 0
    ]

    pre_publish_overall = pre_publish.get("overall", "unknown")
    fact_finding_count = int(fact_check.get("finding_count") or 0)
    diff_overall = diff_check.get("overall", "unknown")

    stop_causes: list[str] = []
    if command_failures:
        stop_causes.append("qa_command_failed")
    if pre_publish_overall != "ok":
        stop_causes.append("pre_publish_not_clean")
    pre_publish_issue_codes = {
        issue.get("code") for issue in pre_publish.get("issues", []) if isinstance(issue, dict)
    }
    if {"future_dated_claim", "publish_time_recheck_required"} & pre_publish_issue_codes:
        stop_causes.append("future_date_guard")
    if fact_finding_count:
        stop_causes.append("fact_check_candidates_remain")
    if diff_overall == "skipped":
        stop_causes.append("note_url_unknown_diff_not_performed")
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
        "overall": "failed" if command_failures else "stopped_before_publish",
        "qa_lane": "return_to_draft" if stop_causes else "clean_local_qa",
        "pre_publish_overall": pre_publish_overall,
        "pre_publish_issues": pre_publish.get("issues", []),
        "fact_check_finding_count": fact_finding_count,
        "fact_check_findings": fact_check.get("findings", []),
        "diff_check": diff_check,
        "diff_fetch_method": diff_check.get("fetch_method", "not_performed"),
        "publication_gate": {
            "state": "stopped_before_publish",
            "stop_causes": stop_causes,
            "human_review_required": True,
            "explicit_current_conversation_approval": False,
        },
        "external_actions_performed": [],
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
    args = parser.parse_args()

    draft = args.draft if args.draft.is_absolute() else ROOT / args.draft
    preview = args.preview or draft.with_suffix(".proof.preview.html")
    preview = preview if preview.is_absolute() else ROOT / preview
    output = args.output if args.output.is_absolute() else ROOT / args.output

    steps = [
        run_step("note_preview", ["scripts/note_preview.py", rel(draft), "-o", rel(preview)]),
        run_step("pre_publish_check", ["scripts/pre_publish_check.py", rel(draft), "--json"]),
        run_step("note_fact_check", ["scripts/note_fact_check.py", "local", rel(draft), "--json"]),
        run_step(
            "note_diff_check",
            ["scripts/note_diff_check.py", args.note_url, rel(draft), *args.phrase, "--json"],
        ),
    ]
    evidence = build_evidence(
        draft=draft,
        preview=preview,
        note_url=args.note_url,
        phrases=args.phrase,
        steps=steps,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    else:
        print(f"evidence_json={rel(output)}")
        print(f"overall={evidence['overall']}")
        print("publication_actions_performed=0")
        print("external_actions_performed=0")

    return 1 if evidence["overall"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
