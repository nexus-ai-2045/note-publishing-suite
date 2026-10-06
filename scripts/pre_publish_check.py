#!/usr/bin/env python3
"""Run local pre-publication checks for a Note draft."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    from note_authorship_gate import evaluate
except ModuleNotFoundError:
    _AUTHORSHIP_SPEC = importlib.util.spec_from_file_location(
        "note_authorship_gate", Path(__file__).with_name("note_authorship_gate.py")
    )
    if _AUTHORSHIP_SPEC is None or _AUTHORSHIP_SPEC.loader is None:
        raise
    _AUTHORSHIP_MODULE = importlib.util.module_from_spec(_AUTHORSHIP_SPEC)
    _AUTHORSHIP_SPEC.loader.exec_module(_AUTHORSHIP_MODULE)
    evaluate = _AUTHORSHIP_MODULE.evaluate


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]

WARNING_PATTERNS = {
    "html_comment": re.compile(r"<!--.*?-->", re.S),
    "todo_marker": re.compile(r"\b(TODO|FIXME)\b", re.I),
    "uncertain_japanese": re.compile(r"(未確認|要確認|仮置き|あとで|TODO|内部メモ)"),
    "private_url_hint": re.compile(r"(localhost|127\.0\.0\.1|file://|C:\\\\Users|/Users/)"),
}

PUBLICATION_DATE_KEYS = {
    "publish_at",
    "publish_date",
    "published_at",
    "publication_at",
    "publication_date",
    "scheduled_at",
    "scheduled_publish_at",
    "target_publish_at",
}

ISO_DATE_PATTERN = re.compile(r"\b(20\d{2})-(0[1-9]|1[0-2])-([0-2]\d|3[01])\b")
JAPANESE_DATE_PATTERN = re.compile(r"\b(20\d{2})年(1[0-2]|0?[1-9])月(3[01]|[12]\d|0?[1-9])日")
RECHECK_REQUIRED_PATTERN = re.compile(
    r"(公開時|公開時点|記事公開時|公開前|投稿時|投稿時点).{0,16}(再確認|要確認)"
    r"|(?:再確認|要確認).{0,16}(公開時|公開時点|記事公開時|公開前|投稿時|投稿時点)"
)

EDITORIAL_REVIEW_SCHEMA = "nps-prepublish-review/v1"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate receipt key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise ValueError(f"invalid JSON constant: {value}")


def load_editorial_review_receipt(path: Path) -> dict[str, Any]:
    """Load a strict receipt; JSON files are data, not authenticity proof."""
    receipt = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_pairs,
        parse_constant=_reject_json_constant,
    )
    if not isinstance(receipt, dict):
        raise ValueError("editorial review receipt must be an object")
    return receipt


def validate_pre_publish_review_receipt(
    receipt: dict[str, Any],
    text: str,
    *,
    article_id: str | None,
    conversation_id: str | None,
) -> list[str]:
    """Validate binding; trusted runtime remains responsible for authenticity."""
    errors: list[str] = []
    if not isinstance(article_id, str) or not article_id.strip():
        errors.append("article_id is missing")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        errors.append("conversation_id is missing")
    if receipt.get("schema_version") != EDITORIAL_REVIEW_SCHEMA:
        errors.append("schema_version is invalid")
    for key, expected in (
        ("article_id", article_id),
        ("conversation_id", conversation_id),
        ("status", "review_required"),
        ("actor", "user"),
        ("draft_sha256", _sha256(text.encode("utf-8"))),
    ):
        if receipt.get(key) != expected:
            errors.append(f"{key} does not match current review target")
    _, body = split_frontmatter(text)
    if receipt.get("body_sha256") != _sha256(body.encode("utf-8")):
        errors.append("body_sha256 does not match current review target")
    if receipt.get("issue_codes") != ["missing_early_takeaway"]:
        errors.append("issue_codes must contain only missing_early_takeaway")
    for key in ("reason", "evidence_ref"):
        if not isinstance(receipt.get(key), str) or not receipt[key].strip():
            errors.append(f"{key} is missing")
    try:
        observed_at = datetime.fromisoformat(receipt.get("observed_at"))
        if observed_at.utcoffset() is None:
            errors.append("observed_at must include timezone")
    except (TypeError, ValueError):
        errors.append("observed_at is invalid")
    return errors


def apply_editorial_review(
    issues: list[dict[str, Any]],
    receipt_path: Path | None,
    text: str,
    *,
    article_id: str | None,
    conversation_id: str | None,
) -> list[dict[str, Any]]:
    """Classify one explicitly reviewed editorial issue without clearing errors."""
    if receipt_path is None:
        return issues
    try:
        receipt = load_editorial_review_receipt(receipt_path)
        errors = validate_pre_publish_review_receipt(
            receipt, text, article_id=article_id, conversation_id=conversation_id
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
    if errors:
        issues.append({
            "severity": "error",
            "code": "invalid_editorial_review_receipt",
            "message": "; ".join(errors),
        })
        return issues
    for issue in issues:
        if issue.get("code") == "missing_early_takeaway":
            issue["severity"] = "review_required"
    return issues


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text

    metadata: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip().strip("'\"")
    metadata["__raw_frontmatter"] = text[4:end]
    return metadata, text[end + len("\n---") :]


def parse_date(value: str) -> date | None:
    match = ISO_DATE_PATTERN.search(value)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None

    match = JAPANESE_DATE_PATTERN.search(value)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    return None


def publication_date_from_metadata(metadata: dict[str, str]) -> date | None:
    for key in PUBLICATION_DATE_KEYS:
        value = metadata.get(key)
        if not value:
            continue
        parsed = parse_date(value)
        if parsed:
            return parsed
    return None


def find_future_date_issues(body: str, publication_date: date | None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not publication_date:
        return issues

    seen: set[tuple[int, str]] = set()
    for line_no, line in enumerate(body.splitlines(), 1):
        for pattern in (ISO_DATE_PATTERN, JAPANESE_DATE_PATTERN):
            for match in pattern.finditer(line):
                parsed = parse_date(match.group(0))
                if not parsed or parsed <= publication_date:
                    continue
                key = (line_no, match.group(0))
                if key in seen:
                    continue
                seen.add(key)
                issues.append(
                    {
                        "severity": "warning",
                        "code": "future_dated_claim",
                        "message": (
                            f"date {match.group(0)} is after publication date "
                            f"{publication_date.isoformat()}"
                        ),
                        "line": line_no,
                        "date": match.group(0),
                        "publication_date": publication_date.isoformat(),
                        "snippet": line.strip()[:180],
                    }
                )
    return issues


def find_recheck_issues(body: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for line_no, line in enumerate(body.splitlines(), 1):
        if not RECHECK_REQUIRED_PATTERN.search(line):
            continue
        issues.append(
            {
                "severity": "warning",
                "code": "publish_time_recheck_required",
                "message": "publication-time recheck marker found",
                "line": line_no,
                "snippet": line.strip()[:180],
            }
        )
    return issues


def collect_issues(text: str) -> list[dict[str, Any]]:
    metadata, body = split_frontmatter(text)
    publication_date = publication_date_from_metadata(metadata)
    issues: list[dict[str, Any]] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            issues.append({"severity": "error", "code": "secret_like_value", "message": "secret-like value found"})
    for code, pattern in WARNING_PATTERNS.items():
        if pattern.search(text):
            issues.append({"severity": "warning", "code": code, "message": f"{code} found"})
    if len(text.strip()) < 400:
        issues.append({"severity": "warning", "code": "short_draft", "message": "draft is very short"})
    title_match = re.search(r"^title:[ \t]*(.*)$", metadata.get("__raw_frontmatter", ""), re.M)
    frontmatter_title = title_match.group(1).strip() if title_match else metadata.get("title", "")
    quote = ""
    for index, char in enumerate(frontmatter_title):
        if char in "\"'" and (index == 0 or frontmatter_title[index - 1] != "\\"):
            quote = "" if quote == char else char if not quote else quote
        elif char == "#" and not quote and (index == 0 or frontmatter_title[index - 1].isspace()):
            frontmatter_title = frontmatter_title[:index].strip()
            break
    title_is_quoted = len(frontmatter_title) >= 2 and frontmatter_title[0] == frontmatter_title[-1] and frontmatter_title[0] in "\"'"
    if title_is_quoted:
        frontmatter_title = frontmatter_title[1:-1].strip()
    non_string_title = not title_is_quoted and (
        frontmatter_title.lower() in {"true", "false", "yes", "no", "on", "off", ".nan", ".inf", "+.inf", "-.inf"}
        or frontmatter_title.startswith(("[", "{", "*", "&", "!", ">", "|", "- "))
        or bool(re.fullmatch(r"[-+]?(?:0[xX][0-9a-fA-F_]+|0[oO][0-7_]+|0[bB][01_]+|(?:\d[\d_]*(?:\.[\d_]*)?|\.[\d_]+)(?:[eE][-+]?\d[\d_]*)?)", frontmatter_title))
        or bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[Tt ]\S+)?", frontmatter_title))
    )
    if frontmatter_title.lower() in {"null", "~"} or non_string_title:
        frontmatter_title = ""
    if not re.search(r"^#\s+\S+", body, re.M) and not frontmatter_title:
        issues.append({"severity": "warning", "code": "missing_h1", "message": "本文H1またはfrontmatterのtitleがありません"})
    intro = body[:900]
    if not re.search(r"(先に結論|結論から|この記事で.{0,80}(分かる|伝える|整理|やる)|要するに|持ち帰)", intro, re.S):
        issues.append({
            "severity": "error",
            "code": "missing_early_takeaway",
            "message": "冒頭900字以内に、先に伝える結論または読後の持ち帰りがありません",
        })
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip() and not part.startswith("---")]
    prose_paragraphs = [part for part in paragraphs if not re.match(r"^(?:[-*+] |\d+\. )", part)]
    if any(len(re.sub(r"\s+", "", part)) > 500 for part in prose_paragraphs):
        issues.append({"severity": "warning", "code": "long_paragraph", "message": "500字を超える段落があります"})
    if len(re.findall(r"^##\s+", body, re.M)) < 2 and len(body) >= 1200:
        issues.append({"severity": "warning", "code": "few_section_headings", "message": "長文に対して小見出しが少なすぎます"})
    issues.extend(find_future_date_issues(body, publication_date))
    issues.extend(find_recheck_issues(body))
    return issues


def collect_production_structure_issues(text: str) -> list[dict[str, str]]:
    """Fail closed on heading structure needed by the live Note TOC."""
    body = re.sub(r"\A---\s*.*?\s*---\s*", "", text, count=1, flags=re.S)
    headings = [
        (len(match.group(1)), match.group(2).strip())
        for match in re.finditer(r"^(#{1,6})\s+(\S.*)$", body, re.M)
    ]
    issues: list[dict[str, str]] = []
    h2_count = sum(level == 2 for level, _ in headings)
    if len(body) >= 1200 and h2_count < 2:
        issues.append({
            "severity": "error",
            "code": "insufficient_section_headings",
            "message": "production_candidate の長文には、Note目次の親になるH2見出しが2件以上必要です",
        })

    previous_level: int | None = None
    seen_h2 = False
    for level, title in headings:
        if level == 1:
            previous_level = 1
            continue
        if level == 2:
            seen_h2 = True
        invalid = (level >= 3 and not seen_h2) or (
            previous_level is not None and level > previous_level + 1
        )
        if invalid:
            issues.append({
                "severity": "error",
                "code": "invalid_heading_hierarchy",
                "message": f"見出し階層が不正です: H{level} {title}",
            })
            break
        previous_level = level
    return issues



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("--fix", action="store_true", help="Remove HTML comments only; other issues remain manual.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--authorship-evidence", type=Path)
    parser.add_argument("--article-id")
    parser.add_argument("--conversation-id")
    parser.add_argument("--prepublish-review-receipt", type=Path)
    args = parser.parse_args()

    text = args.draft.read_text(encoding="utf-8")
    if args.fix:
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        args.draft.write_text(text, encoding="utf-8", newline="\n")

    issues = collect_issues(text)
    issues = apply_editorial_review(
        issues,
        args.prepublish_review_receipt,
        text,
        article_id=args.article_id,
        conversation_id=args.conversation_id,
    )
    frontmatter_match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, re.S)
    lane_match = re.search(r"^article_lane:\s*['\"]?([^'\"\s]+)['\"]?\s*$", frontmatter_match.group(1), re.M) if frontmatter_match else None
    lane = lane_match.group(1) if lane_match else None
    allowed_lanes = {"production_candidate", "exploratory_draft", "editor_fixture", "continuation_article"}
    if frontmatter_match and lane not in allowed_lanes:
        issues.append({"severity": "error", "code": "missing_or_invalid_article_lane", "message": "article_lane がないか未定義です"})
    if lane == "production_candidate":
        voice_match = re.search(r"^voice_profile:\s*['\"]?([^'\"\n]+)['\"]?\s*$", frontmatter_match.group(1), re.M) if frontmatter_match else None
        voice_profile = voice_match.group(1).strip() if voice_match else ""
        if not voice_profile.startswith("obsidian:"):
            issues.append({
                "severity": "error",
                "code": "missing_obsidian_voice_profile",
                "message": "production_candidate には Obsidian 読み戻し由来の voice_profile が必要です",
            })
        issues.extend(collect_production_structure_issues(text))
        evidence = args.authorship_evidence or args.draft.with_suffix(".authorship.json")
        try:
            detail = evaluate(args.draft, evidence)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append({"severity": "error", "code": "authorship_gate_execution_failed", "message": str(exc)})
        else:
            if detail["overall"] == "blocked":
                issues.append({
                    "severity": "error",
                    "code": "unverified_personal_voice",
                    "message": f"本人語り {detail['unresolved_count']} 件に根拠確認がありません",
                })
    result = {
        "draft": str(args.draft),
        "overall": "error" if any(i["severity"] == "error" for i in issues) else (
            "review_required" if any(i["severity"] == "review_required" for i in issues)
            else ("warning" if issues else "ok")
        ),
        "issues": issues,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"overall={result['overall']}")
        for issue in issues:
            print(f"{issue['severity']}:{issue['code']} {issue['message']}")
    return 1 if result["overall"] in {"error", "review_required"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
