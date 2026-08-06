#!/usr/bin/env python3
"""本人語りの無根拠な作文と、比較元からの無断短縮を停止する。"""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import hashlib
import json
import re
from pathlib import Path

PERSONAL = re.compile(
    r"(?:私|僕|俺|自分|わたし|ぼく).{0,80}(?:感じ|思|考え|体験|経験|見た|聞いた|試した|やってみ|気づ|分か|つかん|理解|役に立)"
    r"|(?:初見|その場|あとで|今回).{0,60}(?:驚|戸惑|腑に落ち|役に立|分からな|理解でき)"
    r"|(?:実際に役に立った|視聴者は0人)"
)


def body_lines(text: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    start = 0
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                start = index + 1
                break
    return [(i + 1, line.strip()) for i, line in enumerate(lines[start:], start) if line.strip()]


def excerpt_id(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def scan(text: str) -> list[dict[str, object]]:
    return [
        {"line": line_no, "excerpt": line, "excerpt_id": excerpt_id(line)}
        for line_no, line in body_lines(text)
        if PERSONAL.search(line)
    ]


def draft_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frontmatter_fields(text: str) -> dict[str, str]:
    """依存を増やさず、短縮gateに必要な単純scalarだけを読む。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip("\"'")
    return fields


def resolve_shortening_config(
    draft: Path,
    *,
    cli_source: Path | None,
    cli_budget: float | None,
) -> tuple[Path | None, float, str | None, list[str]]:
    """CLI/frontmatterから比較元を一意に解決し、production契約を検査する。"""
    fields = frontmatter_fields(draft.read_text(encoding="utf-8"))
    production = fields.get("article_lane") == "production_candidate"
    source_value = fields.get("shortening_source")
    frontmatter_source = (
        (draft.parent / source_value).resolve() if source_value else None
    )
    normalized_cli_source = cli_source.resolve() if cli_source else None
    stop_causes: list[str] = []
    if (
        normalized_cli_source is not None
        and frontmatter_source is not None
        and normalized_cli_source != frontmatter_source
    ):
        stop_causes.append("ambiguous_shortening_source")
        source = None
        resolution = None
    elif normalized_cli_source is not None:
        source = normalized_cli_source
        resolution = "cli"
    else:
        source = frontmatter_source
        resolution = "frontmatter" if source else None

    budget_value = fields.get("shortening_budget")
    frontmatter_budget: float | None = None
    if budget_value:
        try:
            frontmatter_budget = float(budget_value)
        except ValueError:
            stop_causes.append("invalid_frontmatter_shortening_budget")
    if (
        cli_budget is not None
        and frontmatter_budget is not None
        and cli_budget != frontmatter_budget
    ):
        stop_causes.append("ambiguous_shortening_budget")
    budget = cli_budget if cli_budget is not None else frontmatter_budget

    if production and source is None and "ambiguous_shortening_source" not in stop_causes:
        stop_causes.append("production_shortening_source_required")
    if production and budget is None:
        stop_causes.append("production_shortening_budget_required")
    if source is not None and not source.is_file():
        stop_causes.append("shortening_source_not_found")
        source = None
    if budget is not None and not 0.0 <= budget < 1.0:
        stop_causes.append("invalid_shortening_budget")
    return source, budget if budget is not None else 0.0, resolution, stop_causes


def meaning_paragraphs(text: str) -> list[str]:
    """frontmatterを除き、空行で区切られた意味段落を返す。"""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                lines = lines[index + 1 :]
                break
    blocks = re.split(r"\n\s*\n", "\n".join(lines))
    return [block.strip() for block in blocks if block.strip()]


def comparable_text(text: str) -> str:
    """Markdown装飾と空白の差を除いた比較用文字列を作る。"""
    text = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[#>*+\-\d.\s]+", "", text)
    return re.sub(r"[\s`*_~]", "", text)


def compare_shortening(
    source_text: str,
    draft_text: str,
    *,
    shortening_budget: float,
    major_phrases: list[str],
) -> dict[str, object]:
    """意味段落の欠落、許容率を超す圧縮、主要句の欠落を検査する。"""
    sources = meaning_paragraphs(source_text)
    drafts = meaning_paragraphs(draft_text)
    normalized_draft = comparable_text(draft_text)
    available = set(range(len(drafts)))
    missing: list[dict[str, object]] = []
    over_budget: list[dict[str, object]] = []

    for source_index, source in enumerate(sources, start=1):
        source_normalized = comparable_text(source)
        candidates: list[tuple[float, int, str]] = []
        for draft_index in available:
            draft_normalized = comparable_text(drafts[draft_index])
            similarity = SequenceMatcher(
                None, source_normalized, draft_normalized
            ).ratio()
            candidates.append((similarity, draft_index, draft_normalized))
        if not candidates:
            missing.append({"source_paragraph": source_index, "excerpt": source[:120]})
            continue
        similarity, draft_index, draft_normalized = max(candidates)
        if similarity < 0.42:
            missing.append({"source_paragraph": source_index, "excerpt": source[:120]})
            continue
        available.remove(draft_index)
        retained_ratio = len(draft_normalized) / max(len(source_normalized), 1)
        reduction_ratio = max(0.0, 1.0 - retained_ratio)
        if reduction_ratio > shortening_budget:
            over_budget.append(
                {
                    "source_paragraph": source_index,
                    "draft_paragraph": draft_index + 1,
                    "reduction_ratio": round(reduction_ratio, 4),
                    "budget": shortening_budget,
                    "excerpt": source[:120],
                }
            )

    missing_phrases = [
        phrase
        for phrase in major_phrases
        if comparable_text(phrase) not in normalized_draft
    ]
    blocked = bool(missing or over_budget or missing_phrases)
    return {
        "checked": True,
        "overall": "blocked" if blocked else "ok",
        "shortening_budget": shortening_budget,
        "source_paragraph_count": len(sources),
        "draft_paragraph_count": len(drafts),
        "missing_paragraph_count": len(missing),
        "missing_paragraphs": missing,
        "over_budget_paragraph_count": len(over_budget),
        "over_budget_paragraphs": over_budget,
        "major_phrase_count": len(major_phrases),
        "missing_major_phrases": missing_phrases,
    }


def load_verified(path: Path | None, draft: Path) -> dict[str, dict[str, object]]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "note-authorship-evidence/v1":
        raise ValueError("unsupported authorship evidence schema")
    if data.get("draft_sha256") != draft_digest(draft):
        raise ValueError("authorship evidence does not match draft digest")
    verified: dict[str, dict[str, object]] = {}
    for claim in data.get("claims", []):
        source = claim.get("source")
        allowed_source = (
            isinstance(source, dict)
            and source.get("kind") in {"current_conversation", "conversation_log", "user_note"}
            and isinstance(source.get("locator"), str)
            and bool(source["locator"].strip())
        )
        excerpt = str(claim.get("excerpt", ""))
        valid = (
            claim.get("status") == "verified"
            and claim.get("actor") == "user"
            and claim.get("observed_at")
            and allowed_source
            and excerpt_id(excerpt) == claim.get("excerpt_id")
        )
        if valid:
            verified[str(claim["excerpt_id"])] = claim
    return verified


def evaluate(
    draft: Path,
    evidence: Path | None,
    *,
    source: Path | None = None,
    shortening_budget: float = 0.0,
    major_phrases: list[str] | None = None,
    source_resolution: str | None = None,
    shortening_stop_causes: list[str] | None = None,
) -> dict[str, object]:
    candidates = scan(draft.read_text(encoding="utf-8"))
    verified = load_verified(evidence, draft)
    unresolved = [item for item in candidates if item["excerpt_id"] not in verified]
    shortening: dict[str, object]
    if shortening_stop_causes:
        shortening = {
            "checked": False,
            "overall": "blocked",
            "stop_causes": shortening_stop_causes,
        }
    elif source is None:
        shortening = {"checked": False, "overall": "not_checked"}
    else:
        shortening = compare_shortening(
            source.read_text(encoding="utf-8"),
            draft.read_text(encoding="utf-8"),
            shortening_budget=shortening_budget,
            major_phrases=major_phrases or [],
        )
        shortening["source"] = str(source)
        shortening["source_resolution"] = source_resolution or "api"
    blocked = bool(unresolved) or shortening["overall"] == "blocked"
    return {
        "schema_version": "note-authorship-gate/v1",
        "draft": str(draft),
        "evidence": str(evidence) if evidence else None,
        "candidate_count": len(candidates),
        "verified_count": len(candidates) - len(unresolved),
        "unresolved_count": len(unresolved),
        "unresolved": unresolved,
        "shortening": shortening,
        "overall": "blocked" if blocked else "ok",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument(
        "--source",
        "--before",
        dest="source",
        type=Path,
        help="短縮検査で比較元とするローカル正本。draftがafterに相当します。",
    )
    parser.add_argument(
        "--shortening-budget",
        type=float,
        default=None,
        help="各意味段落で許容する文字削減率（0.0から1.0未満）。",
    )
    parser.add_argument(
        "--major-phrase",
        action="append",
        default=[],
        help="draftに維持すべき主要句。複数指定できます。",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    source, budget, source_resolution, stop_causes = resolve_shortening_config(
        args.draft,
        cli_source=args.source,
        cli_budget=args.shortening_budget,
    )
    if args.major_phrase and source is None and not stop_causes:
        parser.error("--major-phrase requires --source/--before")
    result = evaluate(
        args.draft,
        args.evidence,
        source=source,
        shortening_budget=budget,
        major_phrases=args.major_phrase,
        source_resolution=source_resolution,
        shortening_stop_causes=stop_causes,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(f"overall={result['overall']} unresolved={result['unresolved_count']}")
    return 1 if result["overall"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
