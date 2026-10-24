#!/usr/bin/env python3
"""Check that a draft accounts for topics extracted from its source conversations."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "note-topic-coverage/v1"
ORIGINS = {"user_speech", "external_source", "ai_suggestion"}
DISPOSITIONS = {"include", "defer", "exclude", "hold"}
CAPTURE_STATUSES = {"complete", "partial", "missing"}
TOPIC_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
MARKER_RE = re.compile(r"^\s*<!--\s*topic:\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*-->\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def _required_string(item: dict[str, Any], key: str, label: str, errors: list[str]) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: {key} is required")
        return ""
    return value.strip()


def draft_markers(text: str) -> list[str]:
    """Read standalone topic comments in Markdown body, excluding code fences."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                lines = lines[index + 1 :]
                break
    markers: list[str] = []
    fence_character = ""
    fence_length = 0
    for line in lines:
        fence = FENCE_RE.match(line)
        if fence:
            run = fence.group(1)
            if not fence_character:
                fence_character, fence_length = run[0], len(run)
            elif run[0] == fence_character and len(run) >= fence_length:
                fence_character, fence_length = "", 0
            continue
        if not fence_character:
            marker = MARKER_RE.match(line)
            if marker:
                markers.append(marker.group(1))
    return markers


def evaluate(ledger: Any, draft: str) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(ledger, dict):
        ledger = {}
        errors.append("ledger must be an object")
    if ledger.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    sources = ledger.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("sources must be a nonempty array")
        sources = []
    source_ids: set[str] = set()
    incomplete_sources: list[str] = []
    for index, source in enumerate(sources):
        label = f"sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{label} must be an object")
            continue
        source_id = _required_string(source, "id", label, errors)
        _required_string(source, "kind", label, errors)
        _required_string(source, "uri", label, errors)
        capture = _required_string(source, "capture_status", label, errors)
        if source_id:
            if source_id in source_ids:
                errors.append(f"duplicate source id: {source_id}")
            source_ids.add(source_id)
        if capture and capture not in CAPTURE_STATUSES:
            errors.append(f"{label}: invalid capture_status: {capture}")
        elif capture in {"partial", "missing"}:
            incomplete_sources.append(source_id or label)

    topics = ledger.get("topics")
    if not isinstance(topics, list) or not topics:
        errors.append("topics must be a nonempty array")
        topics = []
    topic_ids: set[str] = set()
    dispositions: dict[str, str] = {}
    for index, topic in enumerate(topics):
        label = f"topics[{index}]"
        if not isinstance(topic, dict):
            errors.append(f"{label} must be an object")
            continue
        topic_id = _required_string(topic, "id", label, errors)
        _required_string(topic, "topic", label, errors)
        source_id = _required_string(topic, "source_id", label, errors)
        origin = _required_string(topic, "origin", label, errors)
        _required_string(topic, "evidence", label, errors)
        disposition = _required_string(topic, "disposition", label, errors)
        _required_string(topic, "destination", label, errors)
        if topic_id:
            if not TOPIC_ID_RE.fullmatch(topic_id):
                errors.append(f"{label}: invalid topic id: {topic_id}")
            if topic_id in topic_ids:
                errors.append(f"duplicate topic id: {topic_id}")
            topic_ids.add(topic_id)
            dispositions[topic_id] = disposition
        if source_id and source_id not in source_ids:
            errors.append(f"{label}: unknown source_id: {source_id}")
        if origin and origin not in ORIGINS:
            errors.append(f"{label}: invalid origin: {origin}")
        if disposition and disposition not in DISPOSITIONS:
            errors.append(f"{label}: invalid disposition: {disposition}")
        if disposition in {"defer", "exclude"}:
            _required_string(topic, "reason", label, errors)

    markers = draft_markers(draft)
    marker_counts = Counter(markers)
    for topic_id, count in sorted(marker_counts.items()):
        if count > 1:
            errors.append(f"duplicate draft marker: {topic_id}")
        if topic_id not in dispositions:
            errors.append(f"unknown draft marker: {topic_id}")
        elif dispositions[topic_id] != "include":
            errors.append(f"non-included topic marked in draft: {topic_id}")
    missing = sorted(
        topic_id for topic_id, disposition in dispositions.items()
        if disposition == "include" and topic_id not in marker_counts
    )
    errors.extend(f"included topic missing draft marker: {topic_id}" for topic_id in missing)
    errors.extend(f"source capture incomplete: {source_id}" for source_id in incomplete_sources)
    return {
        "schema_version": "note-topic-coverage-check/v1",
        "ok": not errors,
        "coverage_complete": not errors,
        "source_count": len(sources),
        "topic_count": len(topics),
        "disposition_counts": dict(sorted(Counter(dispositions.values()).items())),
        "marker_count": len(markers),
        "incomplete_sources": incomplete_sources,
        "missing_included_topics": missing,
        "stop_causes": errors,
        "guarantee_scope": "ledger_rows_and_draft_markers_only; source_extraction_completeness_requires_review",
        "external_actions_performed": [],
        "publication_actions_performed": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path, help="JSON topic ledger")
    parser.add_argument("draft", type=Path, help="Markdown article draft")
    parser.add_argument("--json", action="store_true", help="Print machine-readable result")
    args = parser.parse_args()
    try:
        ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
        draft = args.draft.read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    result = evaluate(ledger, draft)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print(f"OK topics={result['topic_count']} markers={result['marker_count']}")
    else:
        print("NG")
        for cause in result["stop_causes"]:
            print(f"- {cause}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
