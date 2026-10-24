#!/usr/bin/env python3
"""Build a review context card and review a Note draft before editor work."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PRE_PUBLISH_CHECK = ROOT / "scripts" / "pre_publish_check.py"
PROVENANCE_LABEL_CHECK = ROOT / "scripts" / "provenance_label_check.py"


def load_pre_publish_check():
    spec = importlib.util.spec_from_file_location("pre_publish_check", PRE_PUBLISH_CHECK)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load pre_publish_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_provenance_label_check():
    name = "provenance_label_check"
    spec = importlib.util.spec_from_file_location(name, PROVENANCE_LABEL_CHECK)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load provenance_label_check.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text

    metadata: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text[4:end].splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if line.startswith("  - ") and current_key:
            value = metadata.setdefault(current_key, [])
            if isinstance(value, list):
                value.append(line[4:].strip().strip("'\""))
            continue
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        stripped = value.strip()
        metadata[current_key] = stripped.strip("'\"") if stripped else []
    return metadata, text[end + len("\n---") :]


def normalize_reason_codes(issues: list[dict[str, Any]]) -> list[str]:
    codes: list[str] = []
    for issue in issues:
        code = str(issue.get("code", "")).strip()
        severity = str(issue.get("severity", "warning")).strip() or "warning"
        if code:
            codes.append(f"prepublish_{severity}_{code}")
    return codes


def unique_ordered(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def build_context_card(draft: Path) -> dict[str, Any]:
    text = draft.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(text)
    pre_publish_check = load_pre_publish_check()
    issues = pre_publish_check.collect_issues(text)
    provenance_check = load_provenance_label_check()
    provenance_result = provenance_check.check_draft(draft)
    counts = {label: 0 for label in provenance_check.ALLOWED_LABELS}
    for block in provenance_result.get("blocks", []):
        kind = str(block.get("kind") or "")
        if kind in counts:
            counts[kind] += 1

    title = str(metadata.get("title") or "").strip()
    if not title:
        for line in body.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

    context_card = {
        "schema": "note_review_context_card.v1",
        "draft": str(draft),
        "title": title,
        "status": metadata.get("status", ""),
        "article_lane": metadata.get("article_lane", ""),
        "source_mode": metadata.get("source_mode", ""),
        "publication_gate": metadata.get("publication_gate", ""),
        "external_action": metadata.get("external_action", ""),
        "editor_test_allowed": str(metadata.get("editor_test_allowed", "")).lower()
        == "true",
        "allowed_use": metadata.get("allowed_use", []),
        "not_allowed": metadata.get("not_allowed", []),
        "prepublish": {
            "overall": "error"
            if any(issue.get("severity") == "error" for issue in issues)
            else ("warning" if issues else "ok"),
            "issues": issues,
        },
        "provenance": {
            "overall": provenance_result.get("overall", "skipped"),
            "publication_ready": provenance_result.get("publication_ready", False),
            "counts": counts,
            "hold_count": counts["hold"],
            "findings": provenance_result.get("findings", []),
            "review_handles": [
                {
                    "kind": block.get("kind", ""),
                    "heading": block.get("heading", ""),
                    "quote": block.get("quote", ""),
                    "review": block.get("review", ""),
                }
                for block in provenance_result.get("blocks", [])
            ],
        },
        "external_actions_performed": [],
        "publication_actions_performed": [],
    }
    return context_card


def review_draft(draft: Path) -> dict[str, Any]:
    context_card = build_context_card(draft)
    reason_codes = normalize_reason_codes(context_card["prepublish"]["issues"])
    provenance = context_card["provenance"]
    reason_codes.extend(
        str(finding.get("code"))
        for finding in provenance["findings"]
        if finding.get("code")
    )
    confirmation_questions: list[str] = []

    article_lane = str(context_card.get("article_lane") or "")
    source_mode = str(context_card.get("source_mode") or "")
    publication_gate = str(context_card.get("publication_gate") or "")
    external_action = str(context_card.get("external_action") or "")

    if article_lane != "production_candidate":
        reason_codes.append(f"{article_lane or 'missing_article_lane'}_not_publication_candidate")
    if source_mode == "fixture_only":
        reason_codes.append("fixture_only_source_mode")
    if publication_gate != "human_review_required":
        reason_codes.append("publication_gate_missing_human_review_required")
    else:
        reason_codes.append("publication_gate_human_review_required")
    if external_action != "none":
        reason_codes.append("external_action_not_none")

    has_errors = any(
        issue.get("severity") == "error"
        for issue in context_card["prepublish"]["issues"]
    )
    has_blocking_lane = article_lane != "production_candidate" or source_mode == "fixture_only"
    if has_blocking_lane:
        confirmation_questions.append("この draft は実記事の公開候補ではありません。review 対象から除外しますか。")
    if publication_gate == "human_review_required":
        confirmation_questions.append("Note 公開、予約投稿、SNS 共有を実行しないまま、人間レビューへ渡しますか。")
    if context_card["prepublish"]["issues"]:
        confirmation_questions.append("pre-publish warning / error を解消するまで editor 反映を止めますか。")

    reason_codes = unique_ordered(reason_codes)
    has_provenance_errors = provenance["overall"] == "error"
    if has_errors or has_blocking_lane or has_provenance_errors:
        verdict = "blocked"
    elif context_card["prepublish"]["issues"] or publication_gate == "human_review_required":
        verdict = "needs_confirmation"
    else:
        verdict = "passed"

    return {
        "schema": "note_review_draft.v1",
        "verdict": verdict,
        "reason_codes": reason_codes,
        "confirmation_questions": confirmation_questions,
        "context_card": context_card,
        "external_actions_performed": [],
        "publication_actions_performed": [],
    }


def print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if "verdict" in payload:
        print(f"verdict={payload['verdict']}")
        print("reason_codes=" + ",".join(payload["reason_codes"]))
        for question in payload["confirmation_questions"]:
            print(f"confirmation_question={question}")
    else:
        print(f"context_card={payload['schema']}")
        print(f"draft={payload['draft']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    context_parser = subparsers.add_parser("build-context-card")
    context_parser.add_argument("draft", type=Path)
    context_parser.add_argument("--json", action="store_true")

    review_parser = subparsers.add_parser("review-draft")
    review_parser.add_argument("draft", type=Path)
    review_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.command == "build-context-card":
        payload = build_context_card(args.draft)
        print_payload(payload, args.json)
        return 0

    payload = review_draft(args.draft)
    print_payload(payload, args.json)
    if payload["verdict"] == "blocked":
        return 2
    if payload["verdict"] == "needs_confirmation":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
