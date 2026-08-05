#!/usr/bin/env python3
"""Validate provenance labels for source-pack locked Note drafts."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


TARGET_SOURCE_MODE = "source_pack_locked_with_user_speech_priority"
ALLOWED_LABELS = {
    "user-said",
    "external-fact",
    "assistant-organized",
    "hold",
}
REQUIRED_LABELS = {"user-said", "external-fact", "assistant-organized"}

SOURCE_HINTS = {
    "user-said": (
        "user",
        "speech",
        "transcript",
        "confirmed",
        "conversation",
        "current-conversation",
    ),
    "external-fact": ("external", "official", "public", "source_pack", "source-pack"),
    "assistant-organized": ("assistant", "structure", "synthesis", "transition", "outline"),
    "hold": ("hold", "unresolved", "needs_review", "needs-review"),
}

LABEL_RE = re.compile(
    r"^\s*(?:"
    r"<!--\s*provenance-label:\s*(?P<html_label>[a-z-]+)"
    r"(?:\s*;\s*source:\s*(?P<html_source>[^;>]+?))?\s*-->"
    r"|"
    r"\[provenance-label:\s*(?P<bracket_label>[a-z-]+)"
    r"(?:\s*;\s*source:\s*(?P<bracket_source>[^\]]+))?\]"
    r")\s*$"
)

USER_SPEECH_CUE_RE = re.compile(
    r"(僕|私|ユーザー(?:が|は|曰く)|本人(?:が|は)|体験|user said|user-said)",
    re.I,
)
HOLD_CUE_RE = re.compile(r"(hold|保留|未確認|要確認|追加確認|needs[-_ ]review|unresolved)", re.I)


@dataclass(frozen=True)
class Block:
    label: str
    source: str
    line: int
    text: str
    review: str = ""
    heading: str = ""
    quote: str = ""


MULTILINE_LABEL_RE = re.compile(
    r"^\s*<!--\s*provenance\s*\n(?P<meta>.*?)\n\s*-->\s*$",
    re.M | re.S,
)
PROVENANCE_COMMENT_RE = re.compile(
    r"^\s*<!--\s*(?:provenance-label:.*?-->|provenance\s*\n.*?\n\s*-->)\s*$",
    re.M | re.S,
)


def split_frontmatter(text: str) -> tuple[dict[str, object], str, int]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, 1

    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
    if end is None:
        return {}, text, 1

    frontmatter = parse_simple_yaml(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    body_start_line = end + 2
    return frontmatter, body, body_start_line


def parse_simple_yaml(lines: list[str]) -> dict[str, object]:
    data: dict[str, object] = {}
    current_key: str | None = None
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw.startswith(" ") and ":" in raw:
            key, value = raw.split(":", 1)
            current_key = key.strip()
            value = value.strip()
            if value == "":
                data[current_key] = []
            elif value.lower() in {"true", "false"}:
                data[current_key] = value.lower() == "true"
            else:
                data[current_key] = value.strip("\"'")
            continue
        if current_key and raw.strip().startswith("- "):
            existing = data.setdefault(current_key, [])
            if isinstance(existing, list):
                existing.append(raw.strip()[2:].strip("\"'"))
    return data


def parse_blocks(body: str, start_line: int) -> tuple[list[Block], list[dict[str, object]]]:
    blocks: list[Block] = []
    findings: list[dict[str, object]] = []
    current_label: str | None = None
    current_source = ""
    current_review = ""
    current_start = start_line
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines, current_label, current_source, current_review, current_start
        text = "\n".join(current_lines).strip()
        if text and current_label:
            heading = ""
            quote = ""
            for content_line in text.splitlines():
                stripped = content_line.strip()
                if not heading and re.match(r"^#{1,6}\s+", stripped):
                    heading = re.sub(r"^#{1,6}\s+", "", stripped)
                elif stripped and not stripped.startswith("#"):
                    quote = stripped[:80]
                    break
            blocks.append(
                Block(
                    label=current_label,
                    source=current_source.strip(),
                    line=current_start,
                    text=text,
                    review=current_review.strip(),
                    heading=heading,
                    quote=quote,
                )
            )
        elif text and not all(
            not line.strip() or re.match(r"^#\s+\S", line.strip())
            for line in text.splitlines()
        ):
            findings.append(
                {
                    "severity": "error",
                    "code": "unlabeled_content",
                    "line": current_start,
                    "message": "Content appears before a provenance label.",
                }
            )
        current_lines = []

    lines = body.splitlines()
    offset = 0
    while offset < len(lines):
        line = lines[offset]
        line_no = start_line + offset
        match = LABEL_RE.match(line)
        consumed = 1
        metadata: dict[str, str] = {}
        if not match and re.match(r"^\s*<!--\s*provenance\s*$", line):
            comment_lines = [line]
            cursor = offset + 1
            while cursor < len(lines):
                comment_lines.append(lines[cursor])
                if re.match(r"^\s*-->\s*$", lines[cursor]):
                    break
                cursor += 1
            comment = "\n".join(comment_lines)
            multiline = MULTILINE_LABEL_RE.match(comment)
            if multiline:
                for raw in multiline.group("meta").splitlines():
                    if ":" in raw:
                        key, value = raw.split(":", 1)
                        metadata[key.strip()] = value.strip()
                consumed = len(comment_lines)
        if match:
            flush()
            current_label = match.group("html_label") or match.group("bracket_label") or ""
            current_source = match.group("html_source") or match.group("bracket_source") or ""
            current_review = ""
            current_start = line_no + 1
        elif metadata:
            flush()
            current_label = metadata.get("kind", "")
            current_source = metadata.get("source", "")
            current_review = metadata.get("review", "")
            current_start = line_no + consumed
        else:
            current_lines.append(line)
        if (match or metadata) and current_label not in ALLOWED_LABELS:
            findings.append(
                {
                    "severity": "error",
                    "code": "unknown_label",
                    "line": line_no,
                    "message": f"Unknown provenance label: {current_label}",
                }
            )
        offset += consumed
    flush()
    return blocks, findings


def strip_provenance_comments(text: str) -> str:
    """Remove local provenance metadata before producing a public-body candidate."""
    return re.sub(r"\n{3,}", "\n\n", PROVENANCE_COMMENT_RE.sub("", text)).strip() + "\n"


def source_hint_matches(label: str, source: str) -> bool:
    normalized = source.lower().replace(" ", "_")
    return any(hint in normalized for hint in SOURCE_HINTS[label])


def validate_blocks(blocks: list[Block]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    present = {block.label for block in blocks if block.label in ALLOWED_LABELS}
    for missing in sorted(REQUIRED_LABELS - present):
        findings.append(
            {
                "severity": "error",
                "code": "missing_required_label",
                "label": missing,
                "message": f"Required provenance label is missing: {missing}",
            }
        )

    for block in blocks:
        if block.label not in ALLOWED_LABELS:
            continue
        if not block.source:
            findings.append(
                {
                    "severity": "error",
                    "code": "missing_source_hint",
                    "line": block.line,
                    "label": block.label,
                    "message": "Provenance label must include a compatible source hint.",
                }
            )
        elif not source_hint_matches(block.label, block.source):
            findings.append(
                {
                    "severity": "error",
                    "code": "source_hint_mismatch",
                    "line": block.line,
                    "label": block.label,
                    "source": block.source,
                    "message": "Source hint does not match the provenance label boundary.",
                }
            )

        if block.label == "external-fact" and USER_SPEECH_CUE_RE.search(block.text):
            findings.append(
                {
                    "severity": "error",
                    "code": "user_speech_inside_external_fact",
                    "line": block.line,
                    "label": block.label,
                    "message": "User speech cue appears inside an external-fact block.",
                }
            )
        if block.label == "hold" and not HOLD_CUE_RE.search(block.text):
            findings.append(
                {
                    "severity": "error",
                    "code": "hold_without_review_cue",
                    "line": block.line,
                    "label": block.label,
                    "message": "Hold block must keep an explicit review or unresolved cue.",
                }
            )
        if block.label == "hold":
            findings.append(
                {
                    "severity": "error",
                    "code": "hold_present",
                    "line": block.line,
                    "label": block.label,
                    "message": "Hold block requires human review before public-body export.",
                }
            )
    return findings


def check_draft(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body, body_start_line = split_frontmatter(text)
    source_mode = str(frontmatter.get("source_mode") or "")
    if source_mode != TARGET_SOURCE_MODE:
        return {
            "draft": str(path),
            "ok": True,
            "overall": "skipped",
            "reason": "source_mode_not_targeted",
            "source_mode": source_mode or "unknown",
            "findings": [],
            "labels_seen": [],
            "external_actions_performed": [],
            "publication_actions_performed": [],
        }

    blocks, findings = parse_blocks(body, body_start_line)
    findings.extend(validate_blocks(blocks))
    labels_seen = sorted({block.label for block in blocks if block.label in ALLOWED_LABELS})
    return {
        "draft": str(path),
        "ok": not findings,
        "overall": "ok" if not findings else "error",
        "source_mode": source_mode,
        "labels_seen": labels_seen,
        "block_count": len(blocks),
        "publication_ready": not findings and not any(
            block.label == "hold" for block in blocks
        ),
        "blocks": [
            {
                "kind": block.label,
                "source": block.source,
                "review": block.review,
                "line": block.line,
                "heading": block.heading,
                "quote": block.quote,
            }
            for block in blocks
        ],
        "findings": findings,
        "external_actions_performed": [],
        "publication_actions_performed": [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--public-output",
        type=Path,
        help="検査が通った場合だけ、由来コメントを除いた公開本文候補を書き出す。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = check_draft(args.draft)
    if args.public_output and result["ok"] and result.get("publication_ready"):
        args.public_output.parent.mkdir(parents=True, exist_ok=True)
        args.public_output.write_text(
            strip_provenance_comments(args.draft.read_text(encoding="utf-8")),
            encoding="utf-8",
            newline="\n",
        )
        result["public_output"] = str(args.public_output)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print(f"overall={result['overall']}")
        print(f"source_mode={result['source_mode']}")
        print("external_actions_performed=0")
        print("publication_actions_performed=0")
    else:
        print("overall=error")
        for finding in result["findings"]:
            line = f":{finding.get('line')}" if finding.get("line") else ""
            print(f"error:{finding['code']}{line} {finding['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
