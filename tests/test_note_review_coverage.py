import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from note_review_coverage import check_from_settings, evaluate, recheck, validate_policy


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return sha(path.read_bytes())


@pytest.fixture
def case(tmp_path):
    draft = tmp_path / "draft.md"
    draft.write_text("本文の採用した表現。", encoding="utf-8")
    source = tmp_path / "review.txt"
    source.write_text("論点1は明確化。\n論点2は説明追加。", encoding="utf-8")
    confirmation = tmp_path / "coverage.txt"
    confirmation.write_text("review-oneを原回答と論点ごとに意味照合した。", encoding="utf-8")
    sources = [{"id": "review-one", "path": "review.txt", "sha256": sha(source.read_bytes()),
                "units": [{"id": "unit-one", "quote": "論点1は明確化。", "issue_id": "R01"},
                          {"id": "unit-two", "quote": "論点2は説明追加。", "issue_id": "R02"}],
                "coverage": {"status": "confirmed", "evidence": {
                    "path": "coverage.txt", "sha256": sha(confirmation.read_bytes()),
                    "quote": confirmation.read_text()}}}]
    catalog = {"review_coverage": {"sources": sources, "history": [{"sources": copy.deepcopy(sources)}]}}
    decisions = {"schema": "note-review-decisions/v1", "issues": [
        {"id": "R01", "topic": "表現の明確化", "decision": "pending"},
        {"id": "R02", "topic": "説明の追加", "decision": "pending"}]}
    policy = {"schema": "note-review-coverage-policy/v1", "required": True,
              "decision_log": "decision-log.md", "catalog": "publication-review.json"}
    return {"root": tmp_path, "draft": draft, "catalog": catalog, "decisions": decisions,
            "policy": policy, "prose": "# 判断履歴\n"}


def save(case):
    root = case["root"]
    (root / "decision-log.md").write_text(case["prose"] + "\n```review-coverage\n" +
        json.dumps(case["decisions"], ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
    case["policy"]["catalog_sha256"] = write_json(root / "publication-review.json", case["catalog"])


def run(case):
    save(case)
    return evaluate(case["draft"], case["policy"], base_dir=case["root"])


def decide(case, index, decision="rejected", quote=None):
    issue = case["decisions"]["issues"][index]
    quote = quote or f"{issue['id']} 本人原文: この提案は今回は{decision}とする。"
    case["prose"] += quote + "\n"
    issue.update(decision=decision, reason="今回の意味と構成を維持するため", decision_evidence={
        "path": "decision-log.md", "sha256": sha(quote.encode()), "quote": quote,
        "actor": "author", "kind": "author_statement", "decision": decision,
        "statement": quote.split("本人原文:", 1)[1].strip() if "本人原文:" in quote else quote})
    if decision == "adopted":
        draft_sha = sha(case["draft"].read_bytes())
        issue["application"] = {"status": "applied", "draft_sha256": draft_sha,
                                "quotes": ["採用した表現"]}
        receipt = {"schema": "note-review-verification/v1", "status": "verified",
                   "draft_sha256": draft_sha, "issue_ids": [issue["id"]]}
        name = f"verification-{issue['id']}.json"
        issue["verification"] = {"path": name, "sha256": write_json(case["root"] / name, receipt)}
    return issue


def test_unconfigured_is_optional_and_pure(case):
    assert evaluate(case["draft"], None, base_dir=case["root"])["status"] == "not_required"
    assert not (case["root"] / "decision-log.md").exists()


def test_pending_returns_current_next_and_remaining(case):
    result = run(case)
    assert result["status"] == "blocked"
    assert result["current"] == "R01"
    assert result["remaining"] == ["R01", "R02"]
    assert result["next_action"]
    assert result["semantic_coverage_verified"] is False
    assert result["human_authenticity_verified"] is False


def test_reasoned_rejection_and_hold_do_not_force_adoption(case):
    decide(case, 0, "rejected")
    decide(case, 1, "held")
    result = run(case)
    assert result["status"] == "coverage_verified", result
    assert result["remaining"] == []
    assert result["publication_authorized"] is False


def test_adopted_requires_current_draft_and_receipt(case):
    decide(case, 0, "adopted")
    decide(case, 1, "rejected")
    assert run(case)["status"] == "coverage_verified"


def test_later_conclusion_review_keeps_original_eight_pending(case):
    sources = case["catalog"]["review_coverage"]["sources"]
    source = sources[0]
    source["units"] = [{"id": f"unit-{i}", "quote": "論点1は明確化。", "issue_id": f"R{i:02d}"} for i in range(1, 9)]
    case["catalog"]["review_coverage"]["history"] = [{"sources": copy.deepcopy(sources)}]
    case["decisions"]["issues"] = [{"id": f"R{i:02d}", "topic": f"旧論点{i}", "decision": "pending"} for i in range(1, 9)]
    later = copy.deepcopy(source)
    later.update(id="conclusion", units=[{"id": "conclusion-1", "quote": "論点2は説明追加。", "issue_id": "R09"}])
    later["coverage"] = {"status": "unknown"}
    sources.append(later)
    case["decisions"]["issues"].append({"id": "R09", "topic": "追加結論", "decision": "pending"})
    decide(case, 8, "held")
    result = run(case)
    assert result["remaining"] == [f"R{i:02d}" for i in range(1, 9)]
    assert "source/conclusion:semantic_coverage_unknown" in result["errors"]


@pytest.mark.parametrize("target", ["issue", "unit", "source"])
def test_removed_historical_work_is_detected_even_with_updated_pin(case, target):
    if target == "issue":
        case["decisions"]["issues"].pop(0)
    elif target == "unit":
        case["catalog"]["review_coverage"]["sources"][0]["units"].pop(0)
    else:
        case["catalog"]["review_coverage"]["sources"] = []
    result = run(case)
    assert result["status"] == "blocked"
    assert any("issue_missing" in error or "historical_unit" in error or "sources_or_history_invalid" in error for error in result["errors"])


def test_catalog_rewrite_without_settings_pin_update_stops(case):
    save(case)
    case["catalog"]["review_coverage"]["sources"][0]["units"].pop()
    write_json(case["root"] / "publication-review.json", case["catalog"])
    result = evaluate(case["draft"], case["policy"], base_dir=case["root"])
    assert result["status"] == "blocked"
    assert result["errors"]


@pytest.mark.parametrize("target", ["quote", "source_hash", "unknown", "coverage_quote"])
def test_source_integrity_and_semantic_confirmation_fail_closed(case, target):
    source = case["catalog"]["review_coverage"]["sources"][0]
    if target == "quote":
        source["units"][0]["quote"] = "存在しない原回答"
    elif target == "source_hash":
        source["sha256"] = "0" * 64
    elif target == "unknown":
        source["coverage"]["status"] = "unknown"
    else:
        source["coverage"]["evidence"]["quote"] = "偽の確認引用"
    assert run(case)["status"] == "blocked"


@pytest.mark.parametrize("target", ["ai", "fake_quote", "wrong_path", "missing_actor", "missing_kind", "reason"])
def test_ai_recommendation_is_not_author_adoption(case, target):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    evidence = issue["decision_evidence"]
    if target == "ai":
        quote = "R01 AI推奨: この表現を採用する。"
        case["prose"] += quote + "\n"
        evidence.update(quote=quote, sha256=sha(quote.encode()))
    elif target == "fake_quote":
        evidence["quote"] = "R01 本人原文: 実在しない発言"
        evidence["sha256"] = sha(evidence["quote"].encode())
    elif target == "wrong_path":
        evidence["path"] = "review.txt"
    elif target == "missing_actor":
        evidence.pop("actor")
    elif target == "missing_kind":
        evidence.pop("kind")
    else:
        issue["reason"] = ""
    assert run(case)["status"] == "blocked"


@pytest.mark.parametrize("target", ["missing_application", "missing_quote", "stale_application", "missing_receipt", "stale_receipt", "different_issue", "removed_phrase"])
def test_unapplied_or_other_version_verification_stops(case, target):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    if target == "missing_application":
        issue.pop("application")
    elif target == "missing_quote":
        issue["application"]["quotes"] = ["まだ反映されていない文章"]
    elif target == "stale_application":
        issue["application"]["draft_sha256"] = "0" * 64
    elif target == "missing_receipt":
        issue.pop("verification")
    elif target == "removed_phrase":
        issue["application"]["absent_quotes"] = ["採用した表現"]
    else:
        path = case["root"] / issue["verification"]["path"]
        receipt = json.loads(path.read_text())
        if target == "stale_receipt":
            receipt["draft_sha256"] = "0" * 64
        else:
            receipt["issue_ids"] = ["OTHER"]
        issue["verification"]["sha256"] = write_json(path, receipt)
    assert run(case)["status"] == "blocked"


def test_merge_preserves_each_source_and_unit(case):
    source = case["catalog"]["review_coverage"]["sources"][0]
    source["units"][1]["issue_id"] = "R01"
    case["catalog"]["review_coverage"]["history"] = [{"sources": copy.deepcopy([source])}]
    case["decisions"]["issues"].pop()
    issue = decide(case, 0, "held")
    assert run(case)["status"] == "blocked"
    issue["merges"] = [{"source_id": "review-one", "unit_id": unit["id"],
                        "reason": "同じ編集箇所への重複提案。各出典を保持して検討する"} for unit in source["units"]]
    result = run(case)
    assert result["status"] == "coverage_verified", result
    assert len(result["issues"][0]["sources"]) == 2
    issue["merges"].pop()
    assert run(case)["status"] == "blocked"


@pytest.mark.parametrize("policy", [{}, [], {"schema": "note-review-coverage-policy/v1", "required": True},
                                  {"schema": "note-review-coverage-policy/v1", "required": "true"}])
def test_malformed_policy_stops(case, policy):
    with pytest.raises(ValueError):
        validate_policy(policy)
    assert evaluate(case["draft"], policy, base_dir=case["root"])["status"] == "blocked"


def test_malformed_or_duplicate_machine_blocks_stop(case):
    save(case)
    path = case["root"] / "decision-log.md"
    original = path.read_text()
    path.write_text(original + original)
    assert evaluate(case["draft"], case["policy"], base_dir=case["root"])["status"] == "blocked"
    path.write_text("```review-coverage\n[]\n```\n")
    assert evaluate(case["draft"], case["policy"], base_dir=case["root"])["status"] == "blocked"


def test_reworded_meaning_has_unknown_mapping_not_omission(case):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    case["draft"].write_text("本文の同じ意味を持つ言い換え。", encoding="utf-8")
    current_sha = sha(case["draft"].read_bytes())
    issue["application"]["draft_sha256"] = current_sha
    receipt_path = case["root"] / issue["verification"]["path"]
    receipt = json.loads(receipt_path.read_text())
    receipt["draft_sha256"] = current_sha
    issue["verification"]["sha256"] = write_json(receipt_path, receipt)
    result = run(case)
    assert result["status"] == "blocked"
    assert "R01:application_mapping_unknown" in result["errors"]
    assert result["issues"][0]["application"] == "unknown"
    assert result["issues"][0]["claimed_application"] == "applied"
    assert "意味を再確認" in result["next_action"]
    assert issue["decision"] == "adopted"


def test_empty_inventory_requires_explicit_no_findings_evidence(case):
    source = case["catalog"]["review_coverage"]["sources"][0]
    source["units"] = []
    case["catalog"]["review_coverage"]["history"] = []
    case["decisions"]["issues"] = []
    assert run(case)["status"] == "blocked"
    proof_path = case["root"] / "no-findings.txt"
    proof_path.write_text("review-oneは提案の意味を再確認し、対応すべき論点なしと判断した。", encoding="utf-8")
    source["coverage"]["no_findings"] = {"reason": "総合評価のみで個別の提案はなかった", "evidence": {
        "path": "no-findings.txt", "sha256": sha(proof_path.read_bytes()), "quote": proof_path.read_text()}}
    assert run(case)["status"] == "coverage_verified"


def test_duplicate_decision_key_fails_closed_with_captured_inputs(case):
    decide(case, 0, "adopted")
    decide(case, 1, "held")
    save(case)
    path = case["root"] / "decision-log.md"
    path.write_text(path.read_text().replace('"decision": "adopted"', '"decision": "pending", "decision": "adopted"'))
    result = evaluate(case["draft"], case["policy"], base_dir=case["root"])
    assert result["status"] == "blocked"
    assert any("duplicate_json_key" in error for error in result["errors"])
    assert str(path.resolve()) in result["input_hashes"]
    assert result["selected_paths"][str(path.absolute())] == str(path.resolve())


@pytest.mark.parametrize("draft_text", ["---\nexample: 採用した表現\n---\n未反映の本文。", "<!--採用した表現-->未反映の本文。"])
def test_metadata_or_comment_is_not_body_application(case, draft_text):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    case["draft"].write_text(draft_text, encoding="utf-8")
    current_sha = sha(case["draft"].read_bytes())
    issue["application"]["draft_sha256"] = current_sha
    receipt_path = case["root"] / issue["verification"]["path"]
    receipt = json.loads(receipt_path.read_text())
    receipt["draft_sha256"] = current_sha
    issue["verification"]["sha256"] = write_json(receipt_path, receipt)
    result = run(case)
    assert result["status"] == "blocked"
    assert "R01:application_mapping_unknown" in result["errors"]


def test_recheck_detects_input_changed_after_inner_gate(case):
    decide(case, 0, "rejected")
    decide(case, 1, "held")
    result = run(case)
    assert result["status"] == "coverage_verified"
    assert recheck(result) == []
    unchanged = copy.deepcopy(result)
    (case["root"] / "review.txt").write_text("後から変わった原回答。", encoding="utf-8")
    assert recheck(result) == ["review_coverage:input_changed_after_check"]
    assert result == unchanged


@pytest.mark.parametrize("statement", ["この提案は却下します。", "今回は採用しない。", "今回はrejectedとする。", "I reject this suggestion."])
def test_rejection_statement_cannot_be_promoted_to_adoption(case, statement):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    quote = f"R01 本人原文: {statement}"
    case["prose"] += quote + "\n"
    issue["decision_evidence"].update(quote=quote, statement=statement, sha256=sha(quote.encode()), decision="adopted")
    result = run(case)
    assert result["status"] == "blocked"
    assert "R01:author_decision_evidence_invalid" in result["errors"]


@pytest.mark.parametrize("decision, statement", [("adopted", "この提案を採用します。"), ("adopted", "I accept this suggestion."),
    ("rejected", "今回は見送ります。"), ("rejected", "I reject this suggestion."),
    ("held", "この案は理由を付けて保留します。"), ("held", "I defer this suggestion.")])
def test_explicit_author_statement_supports_its_outcome(case, decision, statement):
    issue = decide(case, 0, decision)
    decide(case, 1, "held")
    quote = f"R01 Author: {statement}"
    case["prose"] += quote + "\n"
    issue["decision_evidence"].update(quote=quote, statement=statement, sha256=sha(quote.encode()))
    assert run(case)["status"] == "coverage_verified"


@pytest.mark.parametrize("statement", ["採用するか保留するかを検討中。", "AI recommendation: I accept this suggestion.",
    "AI推奨: この案を採用する。", "この文章の意味は変えずにしておく。"])
def test_ambiguous_or_ai_recommendation_statement_stays_unknown(case, statement):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    quote = f"R01 本人原文: {statement}"
    case["prose"] += quote + "\n"
    issue["decision_evidence"].update(quote=quote, statement=statement, sha256=sha(quote.encode()))
    assert run(case)["status"] == "blocked"


def test_evidence_outcome_must_match_row_and_statement_must_be_author_attributed(case):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    issue["decision_evidence"]["decision"] = "rejected"
    assert run(case)["status"] == "blocked"
    issue["decision_evidence"]["decision"] = "adopted"
    quote = "R01 AI推奨: 採用します。本人原文: 今回は見送ります。"
    case["prose"] += quote + "\n"
    issue["decision_evidence"].update(quote=quote, statement="採用します。", sha256=sha(quote.encode()))
    assert run(case)["status"] == "blocked"


def test_decision_and_verification_refs_belong_to_log_not_caller_directory(case):
    decide(case, 0, "adopted")
    decide(case, 1, "held")
    save(case)
    policy = dict(case["policy"], decision_log=str(case["root"] / "decision-log.md"),
                  catalog=str(case["root"] / "publication-review.json"))
    unrelated = case["root"] / "unrelated-packet-folder"
    result = evaluate(case["draft"], policy, base_dir=unrelated)
    assert result["status"] == "coverage_verified", result
    assert recheck(result) == []
    assert str(case["root"] / "verification-R01.json") in result["input_hashes"]


@pytest.mark.parametrize("attributed, statement", [
    ("採用するとは言っていない。", "採用するとは言っていない。"),
    ("採用するかはまだ決めていない。", "採用するかはまだ決めていない。"),
    ("採用する。ただし今回は採用しない", "採用する。ただし今回は採用しない"),
    ("採用する。ただし今回は採用しない", "採用する。"),
    ("採用する。\nただし今回は採用しない。", "採用する。"),
    ("採用するのは意味を確認してから。", "採用するのは意味を確認してから。"),
    ("I accept this proposal if the meaning is verified.", "I accept this proposal if the meaning is verified."),
    ("I do not say I accept this proposal.", "I do not say I accept this proposal."),
])
def test_qualified_negated_or_trimmed_author_text_never_proves_adoption(case, attributed, statement):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    quote = "R01 本人原文: " + attributed
    case["prose"] += quote + "\n"
    issue["decision_evidence"].update(quote=quote, statement=statement, sha256=sha(quote.encode()))
    result = run(case)
    assert result["status"] == "blocked"
    assert "R01:author_decision_evidence_invalid" in result["errors"]


@pytest.mark.parametrize("statement", ["採用する。", "この3点を採用する。", "I accept this proposal."])
def test_narrow_complete_author_adoption_statements(case, statement):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    quote = "R01 本人原文: " + statement
    case["prose"] += quote + "\n"
    issue["decision_evidence"].update(quote=quote, statement=statement, sha256=sha(quote.encode()))
    assert run(case)["status"] == "coverage_verified"


def test_optional_policy_allows_valid_future_storage_directories(case):
    root = case["root"]
    (root / "profile.md").write_text("本人の文体を優先する。", encoding="utf-8")
    settings = root / "settings.json"
    write_json(settings, {"schema_version": "nps-workspace-settings/v1", "workspace_root": ".",
        "storage": {"drafts": "drafts", "sources": "sources", "feedback": "future-feedback"},
        "style": {"default_profile": "profile.md", "article_profiles": {}}})
    assert not (root / "future-feedback").exists()
    result = check_from_settings(case["draft"], settings, "example")
    assert result["status"] == "not_required", result
    assert result["errors"] == []
    assert recheck(result) == []
    assert not (root / "future-feedback").exists()


@pytest.mark.parametrize("actual_record", [
    "R01 本人原文: 採用する。ただし今回は採用しない。",
    "R01 本人原文: 採用する。\nただし今回は採用しない。",
    "R01 本人原文: 採用する。\n\nただし今回は採用しない。",
    "説明中の例: R01 本人原文: 採用する。",
    "```text\nR01 本人原文: 採用する。\n```",
    "```text\n```not-a-closing-fence\nR01 本人原文: 採用する。\n```",
    "<!--\nR01 本人原文: 採用する。\n-->",
])
def test_evidence_quote_cannot_truncate_or_fake_actual_author_record(case, actual_record):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    other_quote = case["decisions"]["issues"][1]["decision_evidence"]["quote"]
    case["prose"] = "# 判断履歴\n" + actual_record + "\n## R02\n" + other_quote + "\n"
    quote = "R01 本人原文: 採用する。"
    issue["decision_evidence"].update(quote=quote, statement="採用する。", sha256=sha(quote.encode()))
    result = run(case)
    assert result["status"] == "blocked"
    assert "R01:author_decision_evidence_invalid" in result["errors"]


def test_complete_record_can_include_preceding_issue_heading(case):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    quote = "## R01\n\n本人原文: 採用する。"
    other = "## R02\nR02 本人原文: この提案は今回はheldとする。\n"
    case["prose"] = "# 判断履歴\n" + quote + "\n\n" + other
    issue["decision_evidence"].update(quote=quote, statement="採用する。", sha256=sha(quote.encode()))
    assert run(case)["status"] == "coverage_verified"


def test_crlf_decision_block_and_raw_input_hashes_are_preserved(case):
    decide(case, 0, "rejected")
    decide(case, 1, "held")
    save(case)
    path = case["root"] / "decision-log.md"
    raw = path.read_bytes().replace(b"\n", b"\r\n")
    path.write_bytes(raw)
    result = evaluate(case["draft"], case["policy"], base_dir=case["root"])
    assert result["status"] == "coverage_verified", result
    assert result["decision_log_sha256"] == sha(raw)
    assert result["input_hashes"][str(path)] == sha(raw)
    assert result["input_hashes"][str(case["root"] / "publication-review.json")] == case["policy"]["catalog_sha256"]
    assert path.read_bytes() == raw
    assert recheck(result) == []


@pytest.mark.parametrize("other_id", ["R010", "XR01", "R01X", "R01-extra", "extra-R01", "R01.1", "R01_suffix"])
@pytest.mark.parametrize("location", ["attribution", "heading"])
def test_author_decision_is_bound_to_exact_issue_identifier(case, other_id, location):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    if location == "attribution":
        quote = f"{other_id} 本人原文: 採用する。"
    else:
        quote = f"## {other_id}\n\n本人原文: 採用する。"
    other_quote = case["decisions"]["issues"][1]["decision_evidence"]["quote"]
    case["prose"] = "# 判断履歴\n" + quote + "\n## R02\n" + other_quote + "\n"
    issue["decision_evidence"].update(quote=quote, statement="採用する。", sha256=sha(quote.encode()))
    result = run(case)
    assert result["status"] == "blocked"
    assert "R01:author_decision_evidence_invalid" in result["errors"]


@pytest.mark.parametrize("quote", ["R01 本人原文: 採用する。", "## R01\n\n本人原文: 採用する。", "## 2026-10-30 R01 の採否\n本人原文: 採用する。"])
def test_exact_issue_identifier_supports_full_author_record(case, quote):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    other_quote = case["decisions"]["issues"][1]["decision_evidence"]["quote"]
    case["prose"] = "# 判断履歴\n" + quote + "\n## R02\n" + other_quote + "\n"
    issue["decision_evidence"].update(quote=quote, statement="採用する。", sha256=sha(quote.encode()))
    assert run(case)["status"] == "coverage_verified"


def test_exact_heading_cannot_override_different_attribution_identifier(case):
    issue = decide(case, 0, "adopted")
    decide(case, 1, "held")
    quote = "## R01\nR010 本人原文: 採用する。"
    other_quote = case["decisions"]["issues"][1]["decision_evidence"]["quote"]
    case["prose"] = "# 判断履歴\n" + quote + "\n## R02\n" + other_quote + "\n"
    issue["decision_evidence"].update(quote=quote, statement="採用する。", sha256=sha(quote.encode()))
    assert "R01:author_decision_evidence_invalid" in run(case)["errors"]


def test_disabled_policy_does_not_resolve_any_draft(case):
    result = evaluate(None, {"schema": "note-review-coverage-policy/v1", "required": False}, base_dir=case["root"] / "absent")
    assert result["status"] == "not_required"
    assert result["input_hashes"] == {}


def recorded_decision(case, index=0, decision="adopted"):
    issue = decide(case, index, decision)
    other = case["decisions"]["issues"][1 - index]
    if other["decision"] == "pending":
        decide(case, 1 - index, "held")
    section = (f"## {issue['id']} 以前の本人採否\n"
               "本人原文: この部分は、前に話していたことの意味を保ったままでお願いします。\n\n"
               "続く本人回答: はい、次。\n"
               "採用範囲: 元の長い発言と応答に基づく記録。新しい本人発言へ書き換えない。\n\n")
    other_quote = other["decision_evidence"]["quote"]
    case["prose"] = "# 判断履歴\n" + section + "## 別の採否\n" + other_quote + "\n"
    case["policy"]["allow_recorded_decisions"] = True
    receipt_path = case["root"] / f"verification-{issue['id']}.json"
    receipt = {"schema": "note-review-verification/v1", "status": "verified",
        "draft_sha256": sha(case["draft"].read_bytes()), "issue_ids": [issue["id"]],
        "decision_reviews": [{"issue_id": issue["id"], "decision": decision,
            "record_sha256": sha(section.encode()), "evidence_level": "recorded",
            "status": "verified", "reason": "独立確認で本人の文脈と既存採否・反映範囲を照合した"}]}
    proof = {"path": receipt_path.name, "sha256": write_json(receipt_path, receipt)}
    if decision == "adopted":
        issue["verification"] = dict(proof)
    issue["decision_evidence"] = {"path": "decision-log.md", "kind": "recorded_decision_log",
        "actor": "author", "decision": decision, "evidence_level": "recorded",
        "quote": section, "sha256": sha(section.encode()), "verification": dict(proof)}
    return issue, receipt_path, receipt, section


@pytest.mark.parametrize("decision", ["adopted", "rejected", "held"])
def test_opted_in_recorded_decision_preserves_long_original_context(case, decision):
    issue, _, _, section = recorded_decision(case, decision=decision)
    result = run(case)
    assert result["status"] == "coverage_verified", result
    assert result["human_authenticity_verified"] is False
    assert result["semantic_coverage_verified"] is False
    assert result["issues"][0]["evidence_level"] == "recorded"
    assert issue["decision_evidence"]["quote"] == section
    assert "はい、次。" in (case["root"] / "decision-log.md").read_text()


@pytest.mark.parametrize("optin", [None, False, "true", 1, {}, []])
def test_recorded_mode_requires_explicit_valid_optin(case, optin):
    recorded_decision(case)
    if optin is None:
        case["policy"].pop("allow_recorded_decisions")
    else:
        case["policy"]["allow_recorded_decisions"] = optin
    assert run(case)["status"] == "blocked"


@pytest.mark.parametrize("mutation", ["trim_tail", "trim_heading", "fake_section", "wrong_issue", "wrong_quote_hash",
    "missing_review", "wrong_outcome", "wrong_review_issue", "wrong_record_hash", "wrong_level", "empty_reason",
    "stale_receipt", "missing_member", "forged_file_hash", "duplicate_review", "different_application_receipt"])
def test_recorded_decision_forged_or_partial_bindings_stop(case, mutation):
    issue, path, receipt, section = recorded_decision(case)
    evidence = issue["decision_evidence"]
    if mutation == "trim_tail":
        evidence["quote"] = section.split("続く本人回答:", 1)[0]
    elif mutation == "trim_heading":
        evidence["quote"] = section.split("\n", 1)[1]
    elif mutation == "fake_section":
        evidence["quote"] = section.replace("はい、次。", "存在しない回答。")
    elif mutation == "wrong_issue":
        case["prose"] = case["prose"].replace("## R01 ", "## R010 ")
        evidence["quote"] = section.replace("## R01 ", "## R010 ")
    elif mutation == "wrong_quote_hash":
        evidence["sha256"] = "0" * 64
    elif mutation == "missing_review":
        receipt.pop("decision_reviews")
    elif mutation == "wrong_outcome":
        receipt["decision_reviews"][0]["decision"] = "rejected"
    elif mutation == "wrong_review_issue":
        receipt["decision_reviews"][0]["issue_id"] = "R010"
    elif mutation == "wrong_record_hash":
        receipt["decision_reviews"][0]["record_sha256"] = "0" * 64
    elif mutation == "wrong_level":
        receipt["decision_reviews"][0]["evidence_level"] = "verified"
    elif mutation == "empty_reason":
        receipt["decision_reviews"][0]["reason"] = ""
    elif mutation == "stale_receipt":
        receipt["draft_sha256"] = "0" * 64
    elif mutation == "missing_member":
        receipt["issue_ids"] = ["R010"]
    elif mutation == "forged_file_hash":
        evidence["verification"]["sha256"] = "0" * 64
    elif mutation == "duplicate_review":
        receipt["decision_reviews"].append(dict(receipt["decision_reviews"][0]))
    else:
        alternate = case["root"] / "other-verification.json"
        alternate_sha = write_json(alternate, receipt)
        issue["verification"] = {"path": alternate.name, "sha256": alternate_sha}
    if mutation not in ("wrong_quote_hash", "forged_file_hash", "different_application_receipt"):
        evidence["sha256"] = sha(evidence["quote"].encode())
        if "decision_reviews" in receipt and mutation not in ("wrong_record_hash", "wrong_review_issue"):
            receipt["decision_reviews"][0]["record_sha256"] = evidence["sha256"]
        digest = write_json(path, receipt)
        evidence["verification"]["sha256"] = digest
        issue["verification"]["sha256"] = digest
    result = run(case)
    assert result["status"] == "blocked", result
    assert "R01:author_decision_evidence_invalid" in result["errors"]


def test_recorded_section_includes_child_headings_and_stops_at_equal_heading(case):
    issue, path, receipt, section = recorded_decision(case)
    extended = section + "### 判断の文脈\n本人の文脈を保全する。\n\n"
    case["prose"] = case["prose"].replace(section, extended)
    issue["decision_evidence"].update(quote=extended, sha256=sha(extended.encode()))
    receipt["decision_reviews"][0]["record_sha256"] = issue["decision_evidence"]["sha256"]
    digest = write_json(path, receipt)
    issue["verification"]["sha256"] = digest
    issue["decision_evidence"]["verification"]["sha256"] = digest
    assert run(case)["status"] == "coverage_verified"


def superseded_pending(case):
    base, path, receipt, section = recorded_decision(case)
    pending = {"id": "R02", "topic": "旧対象への任意提案", "decision": "pending",
        "applicability": {"status": "superseded", "by_issue_id": "R01",
            "reason": "既存採用の別表現が旧対象を置き換えていることを独立確認した",
            "absent_quotes": ["論点2は説明追加。"]}}
    case["decisions"]["issues"][1] = pending
    receipt["issue_ids"].append("R02")
    receipt["applicability_reviews"] = [{"issue_id": "R02", "by_issue_id": "R01", "status": "verified",
        "reason": "元提案の対象と現在版の置換を独立照合した", "record_sha256": sha(section.encode())}]
    digest = write_json(path, receipt)
    base["verification"]["sha256"] = digest
    base["decision_evidence"]["verification"]["sha256"] = digest
    pending["applicability"]["verification"] = {"path": path.name, "sha256": digest}
    return base, pending, path, receipt


@pytest.mark.parametrize("forward_reference", [False, True])
def test_source_bound_superseded_applicability_keeps_original_pending_decision(case, forward_reference):
    base, pending, _, _ = superseded_pending(case)
    if forward_reference:
        case["decisions"]["issues"] = [pending, base]
    result = run(case)
    assert result["status"] == "coverage_verified", result
    state = next(row for row in result["issues"] if row["id"] == "R02")
    assert state["decision"] == "pending"
    assert state["applicability"] == "superseded"
    assert result["remaining"] == []
    assert pending["decision"] == "pending"
    assert result["human_authenticity_verified"] is False


@pytest.mark.parametrize("mutation", ["self", "missing_base", "pending_base", "cycle", "missing_target", "target_present",
    "missing_proof", "missing_review", "wrong_base_review", "wrong_record_hash", "stale_receipt", "different_receipt",
    "only_absent", "source_changed", "invalid_adopted_applicability"])
def test_superseded_applicability_requires_full_independent_current_proof(case, mutation):
    base, pending, path, receipt = superseded_pending(case)
    applicability = pending["applicability"]
    if mutation == "self":
        applicability["by_issue_id"] = "R02"
    elif mutation == "missing_base":
        applicability["by_issue_id"] = "UNKNOWN"
    elif mutation == "pending_base":
        base["decision"] = "pending"
    elif mutation == "invalid_adopted_applicability":
        base["applicability"] = {"status": "superseded", "by_issue_id": "R02"}
        case["decisions"]["issues"] = [pending, base]
    elif mutation == "cycle":
        base["decision"] = "pending"
        base["applicability"] = dict(applicability, by_issue_id="R02")
    elif mutation == "missing_target":
        applicability["absent_quotes"] = ["元の回答にも存在しない文字列"]
    elif mutation == "target_present":
        applicability["absent_quotes"] = ["採用した表現"]
    elif mutation == "missing_proof":
        applicability.pop("verification")
    elif mutation == "missing_review":
        receipt.pop("applicability_reviews")
    elif mutation == "wrong_base_review":
        receipt["applicability_reviews"][0]["by_issue_id"] = "R010"
    elif mutation == "wrong_record_hash":
        receipt["applicability_reviews"][0]["record_sha256"] = "0" * 64
    elif mutation == "stale_receipt":
        receipt["draft_sha256"] = "0" * 64
    elif mutation == "different_receipt":
        alternate = case["root"] / "alternate-applicability.json"
        applicability["verification"] = {"path": alternate.name, "sha256": write_json(alternate, receipt)}
    elif mutation == "only_absent":
        pending["applicability"] = {"status": "superseded", "absent_quotes": ["論点2は説明追加。"]}
    else:
        (case["root"] / "review.txt").write_text("論点2は説明追加。でも原回答は改変されている。")
    if mutation in ("missing_review", "wrong_base_review", "wrong_record_hash", "stale_receipt"):
        digest = write_json(path, receipt)
        base["verification"]["sha256"] = digest
        base["decision_evidence"]["verification"]["sha256"] = digest
        applicability["verification"]["sha256"] = digest
    result = run(case)
    assert result["status"] == "blocked", result
    state = next(row for row in result["issues"] if row["id"] == "R02")
    assert state["decision"] == "pending"
    assert state["applicability"] == "unknown"
    assert "R02" in result["remaining"]


@pytest.mark.parametrize("body", [
    "AI推奨: 採用する。\n",
    "本人原文: \n採用範囲: この提案を採用します。\n",
    "本人原文: 「」\n採用範囲: この提案を採用します。\n",
    '本人原文: ""\n採用範囲: この提案を採用します。\n',
    "本人原文: はい、次。\n採用範囲: \n",
    "本人原文: AI推奨: 採用する。\n採用範囲: AI推奨: 採用する。\n",
    "```text\n本人原文: はい、次。\n採用範囲: この提案を採用します。\n```\n",
    "<!--\n本人原文: はい、次。\n採用範囲: この提案を採用します。\n-->\n",
    "本人原文: はい、次。\n本人判断: 却下する。\n",
])
def test_recorded_mode_requires_original_author_text_and_decision_scope(case, body):
    issue, path, receipt, section = recorded_decision(case)
    forged = "## R01 以前の採否\n" + body + "\n"
    case["prose"] = case["prose"].replace(section, forged)
    issue["decision_evidence"].update(quote=forged, sha256=sha(forged.encode()))
    receipt["decision_reviews"][0]["record_sha256"] = issue["decision_evidence"]["sha256"]
    digest = write_json(path, receipt)
    issue["verification"]["sha256"] = digest
    issue["decision_evidence"]["verification"]["sha256"] = digest
    result = run(case)
    assert result["status"] == "blocked"
    assert "R01:author_decision_evidence_invalid" in result["errors"]


def test_recorded_mode_supports_original_inline_reply_and_recorded_scope(case):
    issue, path, receipt, section = recorded_decision(case)
    original = "## R01 以前の採否\n本人は「はい、次。」と応答した。\n採用範囲: 以前の意味と採否の範囲を保持する。\n\n"
    case["prose"] = case["prose"].replace(section, original)
    issue["decision_evidence"].update(quote=original, sha256=sha(original.encode()))
    receipt["decision_reviews"][0]["record_sha256"] = issue["decision_evidence"]["sha256"]
    digest = write_json(path, receipt)
    issue["verification"]["sha256"] = digest
    issue["decision_evidence"]["verification"]["sha256"] = digest
    result = run(case)
    assert result["status"] == "coverage_verified", result
    assert result["human_authenticity_verified"] is False


@pytest.mark.parametrize("heading, body", [
    ("## R010 の本人採否", "R010 本人原文: 採用する。\n本人採用: 採用する。\n関連する未検討の別論点: R01\n"),
    ("## R01 の本人採否", "R010 本人原文: 採用する。\n本人採用: 採用する。\n"),
    ("## 本人採否の履歴", "本人原文: はい、次。\n採用範囲: 以前の意味を保持する。\n関連する論点: R01\n"),
    ("## R01 / R010 の本人採否", "R010 本人原文: 採用する。\n本人採用: 採用する。\n"),
])
def test_recorded_heading_authority_cannot_come_from_incidental_body_or_foreign_author_id(case, heading, body):
    issue, path, receipt, section = recorded_decision(case)
    forged = heading + "\n" + body + "\n"
    case["prose"] = case["prose"].replace(section, forged)
    issue["decision_evidence"].update(quote=forged, sha256=sha(forged.encode()))
    receipt["decision_reviews"][0]["record_sha256"] = issue["decision_evidence"]["sha256"]
    digest = write_json(path, receipt)
    issue["verification"]["sha256"] = digest
    issue["decision_evidence"]["verification"]["sha256"] = digest
    result = run(case)
    assert result["status"] == "blocked"
    assert "R01:author_decision_evidence_invalid" in result["errors"]


def test_recorded_multi_issue_group_heading_preserves_each_review_without_explicit_author_ids(case):
    issue, path, receipt, section = recorded_decision(case)
    group = section.replace("## R01 以前の本人採否", "## R01 / R02 以前の本人採否")
    case["prose"] = "# 判断履歴\n" + group + "## 次の記録\n"
    issue["decision_evidence"].update(quote=group, sha256=sha(group.encode()))
    other = case["decisions"]["issues"][1]
    other["decision_evidence"] = dict(issue["decision_evidence"], decision="held")
    other["decision_evidence"]["verification"] = dict(issue["decision_evidence"]["verification"])
    receipt["issue_ids"].append("R02")
    receipt["decision_reviews"][0]["record_sha256"] = sha(group.encode())
    receipt["decision_reviews"].append({"issue_id": "R02", "decision": "held", "record_sha256": sha(group.encode()),
        "evidence_level": "recorded", "status": "verified", "reason": "同じ保存節から別論点の保留範囲を独立照合した"})
    digest = write_json(path, receipt)
    issue["verification"]["sha256"] = digest
    issue["decision_evidence"]["verification"]["sha256"] = digest
    other["decision_evidence"]["verification"]["sha256"] = digest
    result = run(case)
    assert result["status"] == "coverage_verified", result
    assert [row["evidence_level"] for row in result["issues"]] == ["recorded", "recorded"]
