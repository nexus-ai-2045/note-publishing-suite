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
