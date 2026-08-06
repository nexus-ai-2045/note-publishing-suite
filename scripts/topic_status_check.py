#!/usr/bin/env python3
"""Validate the in-repo topic consolidation ledger against package contracts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "references/topic-consolidation-ledger.md"
ISSUE_DRAFTS = ROOT / "issue-drafts.md"
PDCA_LEDGER = ROOT / "data/note_editor_pdca_failure_patterns.json"
PDCA_CHECKER = ROOT / "scripts/note_editor_pdca_failure_check.py"

REQUIRED_AXIS_IDS = {
    "axis-1",
    "axis-2",
    "axis-3",
    "axis-4",
    "axis-5",
    "axis-6",
}

REQUIRED_ABSORBED = {
    "課題1",
    "課題2",
    "課題3",
    "PDCA failure ledger",
}

ALLOWED_STATUS = {
    "open",
    "absorbed",
    "deferred",
    "blocked_human",
    "done",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_ledger_text(text: str) -> list[str]:
    errors: list[str] = []
    for axis_id in sorted(REQUIRED_AXIS_IDS):
        if axis_id not in text:
            errors.append(f"ledger missing axis id: {axis_id}")

    # Active vocabulary can evolve; require the live set used by current axes.
    for status in ("open", "absorbed", "deferred", "done"):
        if status not in text:
            errors.append(f"ledger missing status token: {status}")

    for needle in (
        "topic_status_check.py",
        "note_editor_pdca_failure_patterns.json",
        "fixture",
        "publication_gate: human_review_required",
        "external_action: none",
    ):
        if needle not in text:
            errors.append(f"ledger missing needle: {needle}")

    # status column values must stay in the closed set when present as `| status |`
    for match in re.finditer(r"\|\s*(axis-\d+)\s*\|[^|]+\|\s*([a-z_]+)\s*\|", text):
        status = match.group(2)
        if status not in ALLOWED_STATUS:
            errors.append(f"unknown status for {match.group(1)}: {status}")

    for item in sorted(REQUIRED_ABSORBED):
        if item not in text:
            errors.append(f"ledger missing absorbed item: {item}")

    return errors


def validate_issue_drafts(text: str) -> list[str]:
    errors: list[str] = []
    # Completed contract items must not still claim raw 「未処理」 without absorbed marker.
    for marker in (
        "課題 1",
        "課題 2",
        "課題 3",
    ):
        if marker not in text:
            errors.append(f"issue-drafts missing section: {marker}")

    if "状態: 吸収済み" not in text and "status: absorbed" not in text:
        # require explicit absorbed markers for contract issues 1-3
        if "課題 1: パッケージ契約" in text and "吸収済み" not in text.split("課題 4:")[0]:
            errors.append("issue-drafts challenges 1-3 must mark 吸収済み")

    if "埋め込み・目次・段落内改行" in text and "吸収済み" not in text:
        errors.append("editor constraint issue must mark 吸収済み")

    return errors


def validate_files() -> list[str]:
    errors: list[str] = []
    for path, label in (
        (LEDGER_PATH, "references/topic-consolidation-ledger.md"),
        (ISSUE_DRAFTS, "issue-drafts.md"),
        (PDCA_LEDGER, "data/note_editor_pdca_failure_patterns.json"),
        (PDCA_CHECKER, "scripts/note_editor_pdca_failure_check.py"),
    ):
        if not path.exists():
            errors.append(f"missing {label}")
    return errors


def build_result() -> dict[str, Any]:
    stop_causes: list[str] = []
    stop_causes.extend(validate_files())
    if LEDGER_PATH.exists():
        stop_causes.extend(validate_ledger_text(_read(LEDGER_PATH)))
    if ISSUE_DRAFTS.exists():
        stop_causes.extend(validate_issue_drafts(_read(ISSUE_DRAFTS)))

    return {
        "ok": not stop_causes,
        "residual_work_zero": not stop_causes,
        "ledger": str(LEDGER_PATH),
        "axes_required": sorted(REQUIRED_AXIS_IDS),
        "external_actions_performed": [],
        "publication_actions_performed": [],
        "stop_causes": stop_causes,
        "guarantee_scope": "topic_ledger_and_absorbed_status_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate topic consolidation ledger wiring."
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = build_result()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print("OK residual_work_zero=true")
    else:
        print("NG")
        for cause in result["stop_causes"]:
            print(f"- {cause}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
