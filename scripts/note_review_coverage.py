from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


DECISION_BLOCK = re.compile(r"^```review-coverage\s*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
AUTHOR_MARKERS = ("本人原文:", "本人指定:", "本人の構造化回答:", "Author:")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _json(raw: str | bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict:
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("review_coverage:duplicate_json_key")
            value[key] = item
        return value

    def invalid_constant(value: str) -> None:
        raise ValueError("review_coverage:nonfinite_json_value")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)


def _body(text: str) -> str:
    text = re.sub(r"\A---\r?\n.*?\r?\n---(?:\r?\n|\Z)", "", text, count=1, flags=re.DOTALL)
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def _statement_supports(statement: str, decision: str) -> bool:
    patterns = {
        "adopted": (
            r"採用(?:する|します|した|しました)[。]?",
            r"この(?:提案|案|3点|三点|修正|表現)を採用(?:する|します)[。]?",
            r"この提案は今回はadoptedとする[。]?",
            r"I (?:accept|adopt) this (?:proposal|suggestion)[.]?",
        ),
        "rejected": (
            r"却下(?:する|します)[。]?",
            r"この(?:提案|案)を却下(?:する|します)[。]?",
            r"(?:今回は)?見送(?:る|ります)[。]?",
            r"(?:今回は)?採用し(?:ない|ません)[。]?",
            r"この提案は今回はrejectedとする[。]?",
            r"I (?:reject|decline) this (?:proposal|suggestion)[.]?",
        ),
        "held": (
            r"保留(?:する|します)[。]?",
            r"この案は(?:理由を付けて)?保留(?:する|します)[。]?",
            r"この提案は今回はheldとする[。]?",
            r"I (?:defer|hold) this (?:proposal|suggestion)[.]?",
        ),
    }
    text = statement.strip()
    for opening, closing in (("「", "」"), ("『", "』"), ("“", "”"), ('"', '"')):
        if text.startswith(opening) and text.endswith(closing):
            text = text[len(opening):-len(closing)]
            break
    return any(re.fullmatch(pattern, text, flags=re.IGNORECASE) for pattern in patterns.get(decision, ()))


def _author_statement(quote: str, statement: Any, decision: str) -> bool:
    if not _text(statement) or not _statement_supports(statement, decision):
        return False
    if sum(quote.count(marker) for marker in AUTHOR_MARKERS) != 1:
        return False
    for marker in AUTHOR_MARKERS:
        if marker in quote:
            attributed = quote.split(marker, 1)[1].strip()
            return attributed == statement.strip()
    return False


def validate_policy(value: Any) -> dict:
    if (not isinstance(value, dict) or value.get("schema") != "note-review-coverage-policy/v1"
            or type(value.get("required")) is not bool):
        raise ValueError("review_coverage_policy_invalid")
    if value["required"] and (not _text(value.get("decision_log"))
            or not _text(value.get("catalog"))
            or not isinstance(value.get("catalog_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", value["catalog_sha256"]) is None):
        raise ValueError("review_coverage_policy_paths_or_pin_invalid")
    return dict(value)


def evaluate(draft: Path, policy: dict | None, *, base_dir: Path) -> dict:
    errors: list[str] = []
    remaining: list[str] = []
    states: list[dict] = []
    hashes: dict[str, str] = {}
    captured: dict[Path, tuple[Path, bytes]] = {}
    result = {
        "status": "blocked", "errors": errors, "current": None,
        "next_action": "レビュー資料と採否の不足を修復する", "remaining": remaining,
        "issues": states, "sources": [], "hashes": {}, "input_hashes": hashes, "selected_paths": {}, "semantic_coverage_verified": False,
        "human_authenticity_verified": False, "publication_authorized": False,
        "limitations": "原文引用・論点対応・採否根拠・現稿と検証版の整合検査です。意味の網羅性や本人性を機械的に証明しません。",
    }
    if policy is None:
        result.update(status="not_required", next_action="任意方針は未採用")
        return result
    try:
        policy = validate_policy(policy)
    except ValueError:
        errors.append("review_coverage_policy_invalid")
        return result
    if not policy["required"]:
        result.update(status="not_required", next_action="任意方針は無効")
        return result

    def read(name: Any, base: Path, label: str) -> tuple[Path, bytes]:
        if not _text(name):
            raise ValueError(f"{label}:path_missing")
        selected = (Path(name) if Path(name).is_absolute() else base / name).absolute()
        actual = selected.resolve(strict=True)
        raw = actual.read_bytes()
        old = captured.setdefault(selected, (actual, raw))
        if old != (actual, raw):
            raise ValueError(f"{label}:input_changed")
        hashes[str(actual)] = _sha(raw)
        result["selected_paths"][str(selected)] = str(actual)
        return actual, raw

    def proof(value: Any, base: Path, label: str) -> tuple[Path, bytes, str]:
        if not isinstance(value, dict):
            raise ValueError(f"{label}:evidence_missing")
        path, raw = read(value.get("path"), base, label)
        if _sha(raw) != value.get("sha256"):
            raise ValueError(f"{label}:hash_mismatch")
        quote = value.get("quote")
        if not _text(quote) or quote not in raw.decode("utf-8-sig"):
            raise ValueError(f"{label}:quote_missing")
        return path, raw, quote

    try:
        draft_path, draft_raw = read(str(draft), Path.cwd(), "draft")
        draft_hash = _sha(draft_raw)
        result["draft_sha256"] = draft_hash
        result["hashes"]["draft"] = draft_hash
        draft_text = _body(draft_raw.decode("utf-8-sig"))
        log_path, log_raw = read(policy.get("decision_log"), base_dir, "decision_log")
        result["decision_log_sha256"] = _sha(log_raw)
        log_text = log_raw.decode("utf-8-sig")
        matches = list(DECISION_BLOCK.finditer(log_text))
        if len(matches) != 1:
            raise ValueError("decision_log:exactly_one_review_coverage_block_required")
        decisions = _json(matches[0].group(1))
        outside = log_text[:matches[0].start()] + log_text[matches[0].end():]
        result["decision_text_sha256"] = _sha(outside.encode("utf-8"))
        if not isinstance(decisions, dict) or decisions.get("schema") != "note-review-decisions/v1":
            raise ValueError("decision_log:schema_invalid")
        issues = decisions.get("issues")
        if not isinstance(issues, list):
            raise ValueError("decision_log:issues_invalid")
        indexed: dict[str, dict] = {}
        for issue in issues:
            if not isinstance(issue, dict) or not _text(issue.get("id")) or not _text(issue.get("topic")):
                raise ValueError("decision_log:issue_invalid")
            if issue["id"] in indexed:
                raise ValueError("decision_log:issue_id_duplicate")
            indexed[issue["id"]] = issue
        catalog_path, catalog_raw = read(policy.get("catalog"), base_dir, "catalog")
        if _sha(catalog_raw) != policy["catalog_sha256"]:
            raise ValueError("catalog:pin_mismatch")
        catalog = _json(catalog_raw)
        coverage = catalog.get("review_coverage") if isinstance(catalog, dict) else None
        if not isinstance(coverage, dict):
            raise ValueError("catalog:review_coverage_missing")
        sources = coverage.get("sources")
        history = coverage.get("history", [])
        if not isinstance(sources, list) or not sources or not isinstance(history, list):
            raise ValueError("catalog:sources_or_history_invalid")

        def inventory(rows: Any, label: str) -> dict[str, dict]:
            if not isinstance(rows, list):
                raise ValueError(f"{label}:sources_invalid")
            mapped = {}
            for row in rows:
                if (not isinstance(row, dict) or not _text(row.get("id"))
                        or not _text(row.get("path")) or not _text(row.get("sha256"))
                        or not isinstance(row.get("units"), list)):
                    raise ValueError(f"{label}:source_invalid")
                if row["id"] in mapped:
                    raise ValueError(f"{label}:source_id_duplicate")
                units = {}
                for unit in row["units"]:
                    if (not isinstance(unit, dict) or not all(_text(unit.get(k)) for k in ("id", "quote", "issue_id"))
                            or unit["id"] in units):
                        raise ValueError(f"{label}:unit_invalid_or_duplicate")
                    units[unit["id"]] = unit
                mapped[row["id"]] = {**row, "units_by_id": units}
            return mapped

        current_sources = inventory(sources, "catalog")
        for past in history:
            if not isinstance(past, dict):
                raise ValueError("history:snapshot_invalid")
            for source_id, old in inventory(past.get("sources"), "history").items():
                now = current_sources.get(source_id)
                if now is None:
                    errors.append(f"{source_id}:historical_source_removed")
                    continue
                if (old["path"], old["sha256"]) != (now["path"], now["sha256"]):
                    errors.append(f"{source_id}:historical_source_changed")
                for unit_id, unit in old["units_by_id"].items():
                    if now["units_by_id"].get(unit_id) != unit:
                        errors.append(f"{source_id}/{unit_id}:historical_unit_removed_or_changed")
        origins: dict[str, list[tuple[str, str]]] = {}
        for source_id, source in current_sources.items():
            label = f"source/{source_id}"
            _, raw = read(source["path"], catalog_path.parent, label)
            if _sha(raw) != source["sha256"]:
                errors.append(f"{label}:hash_mismatch")
            source_text = raw.decode("utf-8-sig")
            source_coverage = source.get("coverage")
            if not isinstance(source_coverage, dict) or source_coverage.get("status") != "confirmed":
                errors.append(f"{label}:semantic_coverage_unknown")
            else:
                try:
                    _, _, quote = proof(source_coverage.get("evidence"), catalog_path.parent, f"{label}/coverage")
                    if source_id not in quote:
                        errors.append(f"{label}:coverage_evidence_not_source_specific")
                except (OSError, ValueError, TypeError) as exc:
                    errors.append(str(exc))
            if not source["units_by_id"]:
                no_findings = source_coverage.get("no_findings") if isinstance(source_coverage, dict) else None
                try:
                    if not isinstance(no_findings, dict) or not _text(no_findings.get("reason")):
                        raise ValueError(f"{label}:empty_inventory_coverage_unknown")
                    _, _, no_findings_quote = proof(no_findings.get("evidence"), catalog_path.parent, f"{label}/no_findings")
                    if (source_id not in no_findings_quote
                            or not any(marker in no_findings_quote for marker in ("論点なし", "no actionable findings"))):
                        raise ValueError(f"{label}:empty_inventory_coverage_unknown")
                except (OSError, ValueError, TypeError) as exc:
                    errors.append(str(exc))
            result["sources"].append({"id": source_id,
                                      "coverage_status": source_coverage.get("status") if isinstance(source_coverage, dict) else "unknown",
                                      "unit_ids": list(source["units_by_id"])})
            for unit_id, unit in source["units_by_id"].items():
                if unit["quote"] not in source_text:
                    errors.append(f"{label}/{unit_id}:quote_missing")
                issue_id = unit["issue_id"]
                origins.setdefault(issue_id, []).append((source_id, unit_id))
                if issue_id not in indexed:
                    errors.append(f"{label}/{unit_id}:issue_missing:{issue_id}")
                    if issue_id not in remaining:
                        remaining.append(issue_id)
        for issue_id, issue in indexed.items():
            issue_errors = []
            if issue_id not in origins:
                issue_errors.append("source_origin_missing")
            issue_origins = origins.get(issue_id, [])
            if len(issue_origins) > 1:
                merges = issue.get("merges")
                if not isinstance(merges, list):
                    issue_errors.append("merge_provenance_required")
                else:
                    declared = []
                    for merge in merges:
                        if (not isinstance(merge, dict) or not all(_text(merge.get(k)) for k in ("source_id", "unit_id", "reason"))):
                            issue_errors.append("merge_provenance_invalid")
                            continue
                        declared.append((merge["source_id"], merge["unit_id"]))
                    if len(set(declared)) != len(declared) or set(declared) != set(issue_origins):
                        issue_errors.append("merge_provenance_incomplete")
            decision = issue.get("decision")
            if decision not in ("pending", "adopted", "rejected", "held"):
                issue_errors.append("decision_invalid")
            elif decision == "pending":
                issue_errors.append("decision_pending")
            else:
                if not _text(issue.get("reason")):
                    issue_errors.append("decision_reason_missing")
                evidence = issue.get("decision_evidence")
                if not isinstance(evidence, dict):
                    issue_errors.append("author_decision_evidence_missing")
                else:
                    try:
                        evidence_path, _ = read(evidence.get("path"), log_path.parent, f"{issue_id}/decision_evidence")
                        quote = evidence.get("quote")
                        if (evidence_path != log_path or evidence.get("actor") != "author"
                                or evidence.get("kind") != "author_statement"
                                or evidence.get("decision") != decision
                                or not _text(quote) or quote not in outside or issue_id not in quote
                                or not _author_statement(quote, evidence.get("statement"), decision)
                                or _sha(quote.encode("utf-8")) != evidence.get("sha256")):
                            issue_errors.append("author_decision_evidence_invalid")
                    except (OSError, ValueError, TypeError):
                        issue_errors.append("author_decision_evidence_invalid")
                if decision == "adopted":
                    application = issue.get("application")
                    if (not isinstance(application, dict) or application.get("status") != "applied"
                            or application.get("draft_sha256") != draft_hash):
                        issue_errors.append("application_missing_or_stale")
                    else:
                        quotes = application.get("quotes")
                        if (not isinstance(quotes, list) or not quotes
                                or any(not _text(quote) or quote not in draft_text for quote in quotes)):
                            issue_errors.append("application_mapping_unknown")
                        absent = application.get("absent_quotes", [])
                        if not isinstance(absent, list) or any(not _text(quote) or quote in draft_text for quote in absent):
                            issue_errors.append("application_removed_quote_still_present")
                    verification = issue.get("verification")
                    try:
                        if not isinstance(verification, dict):
                            raise ValueError("verification_missing")
                        path, raw = read(verification.get("path"), log_path.parent, f"{issue_id}/verification")
                        verified = _json(raw)
                        if (_sha(raw) != verification.get("sha256") or not isinstance(verified, dict)
                                or verified.get("schema") != "note-review-verification/v1"
                                or verified.get("status") != "verified"
                                or verified.get("draft_sha256") != draft_hash
                                or not isinstance(verified.get("issue_ids"), list)
                                or issue_id not in verified["issue_ids"] or path in (draft_path, log_path, catalog_path)):
                            raise ValueError("verification_invalid_or_stale")
                    except (OSError, ValueError, TypeError):
                        issue_errors.append("verification_missing_invalid_or_stale")
            errors.extend(f"{issue_id}:{error}" for error in issue_errors)
            if issue_errors and issue_id not in remaining:
                remaining.append(issue_id)
            claimed_application = issue.get("application", {}).get("status") if isinstance(issue.get("application", {}), dict) else None
            application_state = "unknown" if any(error in issue_errors for error in (
                "application_mapping_unknown", "application_missing_or_stale", "application_removed_quote_still_present")) else claimed_application
            states.append({"id": issue_id, "topic": issue["topic"], "decision": decision,
                           "application": application_state, "claimed_application": claimed_application,
                           "verification": "verified" if decision == "adopted" and not issue_errors else "not_verified",
                           "sources": [{"source_id": source_id, "unit_id": unit_id} for source_id, unit_id in issue_origins],
                           "errors": issue_errors})
        result["selected_paths"].update({str(selected): str(actual) for selected, (actual, _) in captured.items()})
        for selected, (actual, raw) in captured.items():
            if selected.resolve(strict=True) != actual or actual.read_bytes() != raw:
                errors.append("review_coverage:input_changed_during_check")
        if not errors:
            result.update(status="coverage_verified", next_action="同一版の次工程の検査へ進む")
        elif remaining:
            next_action = "引用対応が不明です。現稿の対応引用を改め、意味を再確認する" if any(
                "application_mapping_unknown" in error for error in errors) else "既存decision-logの現在論点から本人採否・反映・同一版検証を再開する"
            result.update(current=remaining[0], next_action=next_action)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError) as exc:
        errors.append("review_coverage:" + str(exc) if isinstance(exc, ValueError) else f"review_coverage:invalid_input:{type(exc).__name__}")
    return result


def recheck(result: dict) -> list[str]:
    try:
        hashes = result["input_hashes"]
        paths = result["selected_paths"]
        if not isinstance(hashes, dict) or not isinstance(paths, dict):
            return ["review_coverage:input_capture_invalid"]
        if any(not isinstance(path, str) or not Path(path).is_absolute()
               or not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None
               or _sha(Path(path).read_bytes()) != sha for path, sha in hashes.items()):
            return ["review_coverage:input_changed_after_check"]
        if any(not isinstance(selected, str) or not isinstance(resolved, str)
               or not Path(selected).is_absolute() or not Path(resolved).is_absolute()
               or str(Path(selected).resolve()) != resolved for selected, resolved in paths.items()):
            return ["review_coverage:path_changed_after_check"]
        return []
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return ["review_coverage:input_unreadable_after_check"]


def check_from_settings(draft: Path, settings: Path, article_id: str | None) -> dict:
    try:
        settings_path = Path(settings)
        actual = settings_path.resolve(strict=True)
        before = actual.read_bytes()
        spec = importlib.util.spec_from_file_location(
            "_nps_loader_bootstrap", Path(__file__).with_name("nps_script_loader.py"))
        if spec is None or spec.loader is None:
            raise ValueError("review_coverage:loader_unavailable")
        loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loader)
        workflow = loader.load_script("note_workflow_gate")
        capture = ({}, {})
        expected, _ = workflow.read_workspace_settings(settings_path, article_id, initial_capture=capture)
        result = evaluate(draft, expected.get("review_coverage_policy"), base_dir=actual.parent)
        result["input_hashes"].update({path: _sha(raw) for path, raw in capture[1].items()})
        result["selected_paths"].update(capture[0])
        result["input_hashes"][str(actual)] = _sha(before)
        result["selected_paths"][str(settings_path.absolute())] = str(actual)
        if settings_path.resolve(strict=True) != actual or actual.read_bytes() != before:
            result["errors"].append("review_coverage:settings_changed_during_check")
            result["status"] = "blocked"
        if final_errors := recheck(result):
            result["errors"].extend(final_errors)
            result["status"] = "blocked"
        return result
    except (OSError, ValueError, TypeError, KeyError, AttributeError, UnicodeError, RuntimeError, RecursionError) as exc:
        return {"status": "blocked", "errors": [f"review_coverage:settings_invalid:{type(exc).__name__}"],
                "current": None, "next_action": "既存settingsと参照資料を修復する", "remaining": [],
                "issues": [], "hashes": {}, "input_hashes": {}, "selected_paths": {},
                "semantic_coverage_verified": False, "human_authenticity_verified": False,
                "publication_authorized": False}
