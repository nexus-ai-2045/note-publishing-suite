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


def _history_entry_errors(entry: dict, target_text: str, target_sha: str, sources: dict) -> list[str]:
    errors = []
    source_id = entry.get("history_source_id")
    if not isinstance(source_id, str) or source_id not in sources:
        return ["history_application_source_unknown"]
    if entry.get("target_sha256") != target_sha:
        errors.append("history_application_target_mismatch")
    if entry.get("evidence_ref") != sources[source_id]["evidence_ref"]:
        errors.append("history_application_reference_mismatch")
    if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
        errors.append("history_application_reason_missing")
    status, before, after = entry.get("application_status"), entry.get("before"), entry.get("after")
    if status == "not_applicable":
        if before != "" or after != "":
            errors.append("history_non_applicable_has_edit")
        return errors
    if status not in ("applied", "preserved"):
        return errors + ["history_application_status_invalid"]
    if (not isinstance(before, str) or not isinstance(after, str) or not after.strip()
            or after.replace("\r\n", "\n") not in target_text):
        return errors + ["history_application_after_missing"]
    if entry.get("target_excerpt_id") != excerpt_id(after):
        errors.append("history_application_excerpt_mismatch")
    if status == "preserved" and before != after:
        errors.append("history_preservation_changed")
    return errors


def _history_body_text(raw: bytes) -> str:
    """hash対象bytesは変えず、LF/CRLF/BOMのfront matterを本文から除く。"""
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return "".join(lines[index + 1:])
        raise ValueError("history適用対象のfront matterが閉じていません")
    return text


def evaluate_history_learning(target: Path, evidence: Path | None, feedback_record: object,
                              reference_hashes: dict[str, str], *,
                              required_sources: list[dict] | None = None) -> dict:
    """履歴候補と現版の実適用を照合する。意味・本人採用は認定しない。"""
    errors: list[str] = []
    result = {"status": "blocked", "errors": errors, "hashes": {},
              "semantic_understanding_verified": False, "human_adoption_verified": False}
    try:
        from note_feedback import read_history_sources, review_entries
        if evidence is None:
            raise ValueError("history evidenceが必要です")
        raw = target.read_bytes()
        if not raw.strip():
            raise ValueError("history適用対象本文が空です")
        target_sha = hashlib.sha256(raw).hexdigest()
        captured = (read_history_sources(evidence, reference_hashes, required_sources=required_sources)
                    if required_sources else read_history_sources(evidence, reference_hashes))
        if captured.get("draft_sha256") != target_sha:
            raise ValueError("history evidenceが現在の本文hashと一致しません")
        target_text = _history_body_text(raw)
        sources = {row["id"]: row for row in captured["sources"]}
        entries = feedback_record.get("entries") if isinstance(feedback_record, dict) else None
        review_entries(entries)
        covered = set()
        applications = []
        for entry in entries:
            if "history_source_id" not in entry:
                continue
            errors.extend(_history_entry_errors(entry, target_text, target_sha, sources))
            source_id = entry.get("history_source_id")
            if isinstance(source_id, str):
                covered.add(source_id)
            applications.append(entry)
        if covered != set(sources):
            errors.append("history_application_coverage_missing")
        if target.read_bytes() != raw or hashlib.sha256(evidence.read_bytes()).hexdigest() != captured["evidence_sha256"]:
            errors.append("history_target_changed_during_read")
        result["hashes"] = {"target": target_sha, "history_sources": captured["evidence_sha256"],
            "applications": hashlib.sha256(json.dumps(applications, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        errors.append("history_learning_unverified")
    result["status"] = "blocked" if errors else "mechanical_ok"
    return result


def check_history_learning_from_settings(draft: Path, settings: Path | None,
                                        article_id: str | None, evidence: Path | None = None, *,
                                        current_draft: Path | None = None) -> dict:
    """外部設定と既存feedbackを束縛し、共通G2を読取り専用で実行する。"""
    result = {"status": "blocked", "errors": [], "hashes": {},
              "semantic_understanding_verified": False, "human_adoption_verified": False}
    try:
        from note_workflow_gate import parse_packet, read_workspace_settings
        from note_feedback import read_feedback_record, validate_history_policy
        original_raw = draft.read_bytes()
        original_sha = hashlib.sha256(original_raw).hexdigest()
        baseline_raw = current_draft.read_bytes() if current_draft is not None else original_raw
        baseline_sha = hashlib.sha256(baseline_raw).hexdigest()
        lane = frontmatter_fields(original_raw.decode("utf-8-sig")).get("article_lane")
        if settings is None:
            if lane in {"production_candidate", "continuation_article"}:
                raise ValueError("制作本文にはsettingsとarticle-idが必要です")
            result["status"] = "not_required"
            return result
        settings_raw = settings.read_bytes()
        config = parse_packet(settings_raw)
        if not isinstance(config, dict):
            raise ValueError("settingsはobjectで指定してください")
        style = config.get("style", {})
        if not isinstance(style, dict):
            raise ValueError("styleはobjectで指定してください")
        if ("history_learning_policy" not in style
                and lane not in {"production_candidate", "continuation_article"}):
            # Partial image-only settings remain usable for non-production QA.
            # A malformed explicit style declaration must not become an opt-out.
            if "default_profile" in style and (
                    not isinstance(style["default_profile"], str) or not style["default_profile"].strip()):
                raise ValueError("default_profileが不正です")
            profiles = style.get("article_profiles", {})
            if not isinstance(profiles, dict):
                raise ValueError("article_profilesが不正です")
            for key, profile in profiles.items():
                refs = profile.get("references") if isinstance(profile, dict) else profile
                if (not isinstance(key, str) or not isinstance(refs, list)
                        or any(not isinstance(ref, str) or not ref.strip() for ref in refs)):
                    raise ValueError("article_profilesの参照path配列が不正です")
            if settings.read_bytes() != settings_raw or draft.read_bytes() != original_raw:
                raise ValueError("settingsまたは本文が検査中に変更されました")
            result["status"] = "not_required"
            result["hashes"] = {"settings": hashlib.sha256(settings_raw).hexdigest(), "target": original_sha}
            return result
        declared_policy = (validate_history_policy(style['history_learning_policy'])
                           if 'history_learning_policy' in style else None)
        if (declared_policy and declared_policy['required']
                and (not isinstance(article_id, str) or not article_id.strip())):
            raise ValueError("history適用対象のarticle-idが必要です")
        expected, dirs = read_workspace_settings(settings, article_id or '')
        if expected.get("settings_sha256") != hashlib.sha256(settings_raw).hexdigest():
            raise ValueError("settingsが検査中に変更されました")
        result["settings_readback"] = expected
        policy = expected.get("history_learning_policy", {})
        if not policy.get("required"):
            if settings.read_bytes() != settings_raw or draft.read_bytes() != original_raw:
                raise ValueError("settingsまたは本文が検査中に変更されました")
            result["status"] = "not_required"
            return result
        record, readback = read_feedback_record(dirs, article_id)
        if current_draft is not None and not current_draft.resolve().is_relative_to(dirs['drafts'].resolve()):
            raise ValueError("現在本文がdrafts保存先の外です")
        evidence_path = evidence or draft.with_suffix(".authorship.json")
        evidence_raw = evidence_path.read_bytes()
        checked = evaluate_history_learning(draft, evidence_path,
                                            record, expected["reference_hashes"],
                                            required_sources=policy.get("required_sources"))
        result.update(checked)
        result["article_id"] = article_id
        result["settings_readback"] = expected
        result["feedback_readback"] = readback
        if (checked["status"] == "mechanical_ok"
                and readback["snapshot_hashes"]["draft"] != baseline_sha):
            result["errors"].append("history_feedback_target_mismatch")
            result["status"] = "blocked"
        if (read_workspace_settings(settings, article_id) != (expected, dirs)
                or read_feedback_record(dirs, article_id)[1] != readback):
            result["errors"].append("history_context_changed_during_read")
            result["status"] = "blocked"
        if (draft.read_bytes() != original_raw
                or (current_draft is not None and current_draft.read_bytes() != baseline_raw)
                or checked.get("hashes", {}).get("target") not in {None, original_sha}
                or evidence_path.read_bytes() != evidence_raw
                or checked.get("hashes", {}).get("history_sources")
                not in {None, hashlib.sha256(evidence_raw).hexdigest()}):
            result["errors"].append("history_target_changed_during_context")
            result["status"] = "blocked"
        if current_draft is not None:
            result['hashes']['current_draft'] = baseline_sha
    except (OSError, ValueError, TypeError, KeyError, AttributeError, UnicodeError, RuntimeError, RecursionError):
        result["errors"].append("history_learning_context_unverified")
        result["status"] = "blocked"
    return result


def scan(text: str) -> list[dict[str, object]]:
    return [
        {"line": line_no, "excerpt": line, "excerpt_id": excerpt_id(line)}
        for line_no, line in body_lines(text)
        if PERSONAL.search(line)
    ]


def draft_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frontmatter_fields(text: str) -> dict[str, str]:
    """公開前検査と著者性検査で共有する単純scalar。キーは小文字へ正規化する。"""
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
        fields[key.strip().lower()] = value.strip().strip("\"'")
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


def load_verified(path: Path | None, draft: Path, *, target_sha256: str | None = None,
                  evidence_raw: bytes | None = None) -> dict[str, dict[str, object]]:
    if path is None or not path.exists():
        return {}
    data = json.loads((evidence_raw if evidence_raw is not None else path.read_bytes()).decode("utf-8"))
    if data.get("schema_version") != "note-authorship-evidence/v1":
        raise ValueError("unsupported authorship evidence schema")
    if data.get("draft_sha256") != (target_sha256 or draft_digest(draft)):
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
    shortening_budget: float | None = None,
    major_phrases: list[str] | None = None,
    source_resolution: str | None = None,
    shortening_stop_causes: list[str] | None = None,
) -> dict[str, object]:
    raw = draft.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    target_sha = hashlib.sha256(raw).hexdigest()
    evidence_raw = evidence.read_bytes() if evidence is not None and evidence.exists() else None
    if shortening_stop_causes is None:
        source, shortening_budget, source_resolution, shortening_stop_causes = (
            resolve_shortening_config(draft, cli_source=source, cli_budget=shortening_budget)
        )
    candidates = scan(text)
    verified = load_verified(evidence, draft, target_sha256=target_sha, evidence_raw=evidence_raw)
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
        source_raw = source.read_bytes()
        shortening = compare_shortening(
            source_raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n"),
            text,
            shortening_budget=shortening_budget if shortening_budget is not None else 0.0,
            major_phrases=major_phrases or [],
        )
        shortening["source"] = str(source)
        shortening["source_resolution"] = source_resolution or "api"
        shortening["source_sha256"] = hashlib.sha256(source_raw).hexdigest()
    blocked = bool(unresolved) or shortening["overall"] == "blocked"
    snapshot_changed = (draft.read_bytes() != raw
                        or (evidence_raw is not None and evidence.read_bytes() != evidence_raw)
                        or (source is not None and shortening.get("checked")
                            and source.read_bytes() != source_raw))
    blocked = blocked or snapshot_changed
    return {
        "schema_version": "note-authorship-gate/v1",
        "draft": str(draft),
        "evidence": str(evidence) if evidence else None,
        "draft_sha256": target_sha,
        "evidence_sha256": hashlib.sha256(evidence_raw).hexdigest() if evidence_raw is not None else None,
        "snapshot_changed": snapshot_changed,
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
    parser.add_argument("--settings", type=Path, help="採用済みの外部workspace設定")
    parser.add_argument("--article-id", help="本文または告知の明示した対象ID")
    parser.add_argument("--history-only", action="store_true", help="既存G2の読取り専用実行。必須設定を省略しない")
    args = parser.parse_args()
    if args.history_only:
        result = check_history_learning_from_settings(args.draft, args.settings, args.article_id, args.evidence)
        if args.settings is None or args.article_id is None:
            result["status"] = "blocked"
            result["errors"].append("history_learning_settings_required")
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["status"] == "mechanical_ok" else 1
    original_raw = args.draft.read_bytes()
    original_sha = hashlib.sha256(original_raw).hexdigest()
    original_evidence = args.evidence.read_bytes() if args.evidence is not None and args.evidence.exists() else None
    source, budget, source_resolution, stop_causes = resolve_shortening_config(
        args.draft,
        cli_source=args.source,
        cli_budget=args.shortening_budget,
    )
    if args.major_phrase and source is None and not stop_causes:
        parser.error("--major-phrase requires --source/--before")
    original_source = source.read_bytes() if source is not None and not stop_causes else None
    result = evaluate(
        args.draft,
        args.evidence,
        source=source,
        shortening_budget=budget,
        major_phrases=args.major_phrase,
        source_resolution=source_resolution,
        shortening_stop_causes=stop_causes,
    )
    if (args.settings is not None
            or frontmatter_fields(args.draft.read_text(encoding="utf-8-sig")).get("article_lane")
            in {"production_candidate", "continuation_article"}):
        history = check_history_learning_from_settings(args.draft, args.settings, args.article_id, args.evidence)
        result["history_learning"] = history
        if history["status"] == "blocked":
            result["overall"] = "blocked"
        if history["status"] == "mechanical_ok" and history["hashes"].get("target") != original_sha:
            result["overall"] = "blocked"
    if (result.get("draft_sha256") != original_sha or args.draft.read_bytes() != original_raw
            or (original_evidence is not None and args.evidence.read_bytes() != original_evidence)
            or (original_evidence is not None
                and result.get("evidence_sha256") != hashlib.sha256(original_evidence).hexdigest())
            or (original_source is not None and source.read_bytes() != original_source)
            or (original_source is not None and result["shortening"].get("checked")
                and result["shortening"].get("source_sha256") != hashlib.sha256(original_source).hexdigest())):
        result["overall"] = "blocked"
        result["snapshot_changed"] = True
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(f"overall={result['overall']} unresolved={result['unresolved_count']}")
    return 1 if result["overall"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
