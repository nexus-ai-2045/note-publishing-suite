"""公開と本文点検を混同せず、実行照合とfeedback保全を負例で検査する。"""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import note_postpublish_review as gate
from note_feedback import read_feedback_record, record_feedback


@pytest.fixture
def packet(tmp_path):
    body = "先に結論。僕は自分の感じ方を言葉にしてみました。\n“I love↑ you↘”いうのを聞いた。"
    observed = dict(schema="note-public-observation/v1", note_id="n123", url="https://note.com/example/n/n123",
                    body=body, captured_at="2026-10-16T00:00:00+09:00", captured_by="codex-internal-browser")
    review = dict(note_id="n123", url=observed["url"], body_sha256=gate.digest(body.encode()),
                  scope="full_public_body", coverage_start=0, coverage_end=len(body),
                  checks=["typos", "omissions", "readability", "voice_preservation"],
                  source_thread_id="fixture-thread", worker_id="fixture-worker",
                  reviewed_at="2026-10-16T00:01:00+09:00", summary="全文を読み誤字・助詞・本人の語り口を点検した。",
                  findings=[])
    evidence = tmp_path / "actual-result.json"
    evidence.write_text(json.dumps(review, ensure_ascii=False))
    observed["editorial_review"] = dict(review, evidence_ref=evidence.name, evidence_sha256=gate.digest(evidence.read_bytes()))
    dirs = {key: tmp_path / key for key in ("sources", "drafts", "feedback")}
    for path in dirs.values(): path.mkdir()
    source, draft = dirs["sources"] / "source.md", dirs["drafts"] / "draft.md"
    source.write_text(body); draft.write_text(body)
    context = dict(dirs=dirs, source=source, prior=source, draft=draft, conversation_id="fixture-thread")
    return observed, evidence, context


def check(packet, **kwargs):
    observed, evidence, context = packet
    return gate.check_postpublish_review(observed, base_dir=evidence.parent,
        feedback_context=context, **kwargs)


def trusted_fixture(review, raw):
    """模擬runtime照合。実agent実行や真正性の運用証明ではない。"""
    return review["worker_id"] == "fixture-worker" and json.loads(raw)["worker_id"] == "fixture-worker"


def rewrite_evidence(packet):
    observed, evidence, _ = packet
    review = observed["editorial_review"]
    evidence.write_text(json.dumps({k: v for k, v in review.items() if k not in {"evidence_ref", "evidence_sha256"}}, ensure_ascii=False))
    review["evidence_sha256"] = gate.digest(evidence.read_bytes())


def test_unpublished_waits_and_lint_alone_cannot_complete(packet):
    assert gate.check_postpublish_review(None)["status"] == "waiting_for_publication"
    packet[0].pop("editorial_review")
    result = check(packet)
    assert result["status"] == "postpublish_review_pending"
    assert result["mechanical"]["status"] == "checked"
    assert result["postpublication_complete"] is False


def test_self_claimed_ai_json_cannot_complete_or_write(packet):
    packet[0]["editorial_review"]["actor"] = "ai"
    rewrite_evidence(packet)
    result = check(packet, write_feedback=True)
    assert result["ai_review"]["status"] == "runtime_confirmation_required"
    assert result["postpublication_complete"] is False
    assert not list(packet[2]["dirs"]["feedback"].iterdir())


@pytest.mark.parametrize("change", ["missing_id", "unresolved_id", "partial", "missing_checks", "wrong_url", "wrong_note", "old_hash", "no_findings", "bad_date", "missing_evidence", "bad_evidence_hash", "evidence_diff", "adopted", "quote_absent"])
def test_incomplete_or_stale_review_blocks(packet, change):
    review = packet[0]["editorial_review"]
    if change == "missing_id": review.pop("worker_id")
    elif change == "unresolved_id": review["worker_id"] = "unknown"
    elif change == "partial": review["coverage_end"] -= 1
    elif change == "missing_checks": review["checks"].pop()
    elif change == "wrong_url": review["url"] = "https://note.com/other/n/n123"
    elif change == "wrong_note": review["note_id"] = "n456"
    elif change == "old_hash": review["body_sha256"] = "0" * 64
    elif change == "no_findings": review.pop("findings")
    elif change == "bad_date": review["reviewed_at"] = None
    elif change == "missing_evidence": review["evidence_ref"] = "missing.json"
    elif change == "bad_evidence_hash": review["evidence_sha256"] = "0" * 64
    elif change == "evidence_diff": packet[1].write_text("{}")
    elif change == "adopted": review["findings"] = [dict(before="いうのを", after="というのを", reason="助詞脱落候補", decision="adopted")]
    else: review["findings"] = [dict(before="存在しない引用", after="修正", reason="候補")]
    if change not in {"missing_evidence", "bad_evidence_hash", "evidence_diff"}: rewrite_evidence(packet)
    assert check(packet, runtime_verifier=trusted_fixture, write_feedback=True)["status"] == "blocked"


def test_body_one_character_change_invalidates_review(packet):
    packet[0]["body"] += "。"
    assert check(packet, runtime_verifier=trusted_fixture)["status"] == "blocked"


def test_runtime_rejection_or_changed_body_during_verification_blocks(packet):
    assert check(packet, runtime_verifier=lambda *_: False)["status"] == "blocked"
    def mutate(*_):
        packet[0]["body"] += "改変"
        return True
    assert check(packet, runtime_verifier=mutate, write_feedback=True)["status"] == "blocked"


def test_zero_findings_requires_feedback_save_then_verifies(packet):
    result = check(packet, runtime_verifier=trusted_fixture)
    assert result["feedback"]["status"] == "save_required" and not result["postpublication_complete"]
    result = check(packet, runtime_verifier=trusted_fixture, write_feedback=True)
    assert result["status"] == "checked" and result["postpublication_complete"]
    assert result["feedback"]["status"] == "saved_verified"
    saved_before = (packet[2]["dirs"]["feedback"] / "n123/feedback.json").read_bytes()
    result = check(packet, runtime_verifier=trusted_fixture)
    assert result["status"] == "checked" and result["postpublication_complete"]
    assert (packet[2]["dirs"]["feedback"] / "n123/feedback.json").read_bytes() == saved_before


def test_proposals_append_pending_preserve_author_and_do_not_change_body(packet):
    observed, _, context = packet
    author = dict(origin="author", decision="adopted", before="", after="本人の語り口", reason="本人採用", evidence_ref="fixture://author")
    record_feedback(context["dirs"], "n123", context["source"], context["draft"], context["prior"], [author], conversation_id="fixture-thread")
    before_source, before_draft = context["source"].read_bytes(), context["draft"].read_bytes()
    observed["editorial_review"]["findings"] = [dict(before="いうのを", after="というのを", reason="助詞の脱落候補。本人判断を待つ")]
    rewrite_evidence(packet)
    for attempt in range(2):
        if attempt:
            new_evidence = packet[1].with_name("next-actual-result.json")
            new_evidence.write_bytes(packet[1].read_bytes())
            observed["editorial_review"]["evidence_ref"] = new_evidence.name
        result = check(packet, runtime_verifier=trusted_fixture, write_feedback=True)
        assert result["status"] == "review_required" and not result["postpublication_complete"]
    saved, _ = read_feedback_record(context["dirs"], "n123")
    assert saved["entries"][0] == author
    assert len(saved["entries"]) == 2 and saved["entries"][1]["decision"] == "pending"
    assert saved["entries"][1]["origin"] == "ai"
    assert (context["source"].read_bytes(), context["draft"].read_bytes()) == (before_source, before_draft)
    assert result["external_actions"] == [] and result["body_changes"] == []


def test_feedback_save_failure_blocks(packet, monkeypatch):
    def fail(*_, **__): raise OSError("fixture save failure")
    monkeypatch.setattr(gate, "record_feedback", fail)
    assert check(packet, runtime_verifier=trusted_fixture, write_feedback=True)["status"] == "blocked"


def test_zero_new_findings_does_not_clear_existing_pending_body_proposal(packet):
    context = packet[2]
    pending = dict(origin="ai", decision="pending", before="いうのを", after="というのを",
                   reason="前回の脱字候補は本人判断待ち", evidence_ref="fixture://previous-review")
    record_feedback(context["dirs"], "n123", context["source"], context["draft"], context["prior"], [pending], conversation_id="fixture-thread")
    result = check(packet, runtime_verifier=trusted_fixture, write_feedback=True)
    assert result["status"] == "review_required" and not result["postpublication_complete"]
    assert result["feedback"]["unresolved_body_proposals"] == [pending]


def test_secret_lint_blocks_before_feedback_snapshot_copy(packet, monkeypatch):
    monkeypatch.setattr(gate, "collect_issues", lambda _: [dict(code="secret_like_value", severity="error")])
    result = check(packet, runtime_verifier=trusted_fixture, write_feedback=True)
    assert result["status"] == "blocked" and not result["postpublication_complete"]
    assert not list(packet[2]["dirs"]["feedback"].iterdir())


def test_cli_records_publication_fact_but_cannot_self_attest_ai(packet, capsys):
    import post_publish
    observed, evidence, context = packet
    observed["title"] = "本人の題名"
    path = evidence.parent / "observation.json"
    path.write_text(json.dumps(observed, ensure_ascii=False))
    assert post_publish.main(["--url", observed["url"], "--draft", str(context["draft"]),
        "--ledger-dir", str(evidence.parent / "ledgers"), "--local-observation", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["postpublication_complete"] is False
    assert result["postpublish_review"]["ai_review"]["status"] == "runtime_confirmation_required"


def test_feedback_writer_erasing_existing_entries_is_rejected(packet, monkeypatch):
    original = gate.record_feedback
    def erase(dirs, note_id, source, draft, prior, entries, **kwargs):
        return original(dirs, note_id, source, draft, prior, [], **kwargs)
    packet[0]["editorial_review"]["findings"] = [dict(before="いうのを", after="というのを", reason="助詞候補")]
    rewrite_evidence(packet)
    monkeypatch.setattr(gate, "record_feedback", erase)
    assert check(packet, runtime_verifier=trusted_fixture, write_feedback=True)["status"] == "blocked"


def replace_public_body(packet, body):
    packet[0]["body"] = body
    packet[0]["title"] = "公開題名は本文と別に観測する"
    review = packet[0]["editorial_review"]
    review.update(body_sha256=gate.digest(body.encode()), coverage_end=len(body))
    packet[2]["source"].write_text(body)
    packet[2]["draft"].write_text(body)
    rewrite_evidence(packet)


def test_plain_public_body_does_not_require_draft_structure(packet):
    body = "僕の感じ方を、今日はそのまま書いておきたい。\n\n" + ("日々の気づきを言葉にする。\n\n" * 90)
    replace_public_body(packet, body)
    result = check(packet, runtime_verifier=trusted_fixture, write_feedback=True)
    assert result["status"] == "checked"
    assert result["postpublication_complete"] is True
    assert not {"missing_h1", "missing_early_takeaway", "few_section_headings", "long_paragraph", "short_draft"} & {i["code"] for i in result["mechanical"]["issues"]}
    from pre_publish_check import collect_issues
    assert any(i["code"] == "missing_early_takeaway" and i["severity"] == "error" for i in collect_issues(body))


@pytest.mark.parametrize("body,code", [("これは内部メモです。公開文へ残さない。", "internal_memo"),
    ("<!-- draft fragment -->", "html_comment"), ("TODO: 本人へ確認", "todo_marker")])
def test_plain_public_body_keeps_safety_and_residue_checks(packet, body, code):
    replace_public_body(packet, body)
    result = check(packet, runtime_verifier=trusted_fixture, write_feedback=True)
    assert any(i["code"] == code for i in result["mechanical"]["issues"])
    if code == "internal_memo":
        assert result["status"] == "review_required" and not result["postpublication_complete"]


def test_plain_public_body_real_secret_pattern_blocks_before_feedback(packet):
    replace_public_body(packet, "公開本文に混入した値 " + "sk-" + "fixture" * 5)
    result = check(packet, runtime_verifier=trusted_fixture, write_feedback=True)
    assert result["status"] == "blocked"
    assert any(i["code"] == "secret_like_value" and i["severity"] == "error" for i in result["mechanical"]["issues"])
    assert not list(packet[2]["dirs"]["feedback"].iterdir())


def test_explicit_article_id_keeps_existing_editorial_feedback(packet):
    observed, evidence, context = packet
    context['article_id'] = 'essay-03'
    record_feedback(context['dirs'], 'essay-03', context['source'], context['draft'], context['prior'],
                    [], conversation_id=context['conversation_id'])
    result = check(packet, runtime_verifier=trusted_fixture, write_feedback=True)
    assert result['postpublication_complete'] is True
    assert result['feedback']['article_id'] == 'essay-03'
    assert (context['dirs']['feedback'] / 'essay-03' / 'feedback.json').exists()
    assert not (context['dirs']['feedback'] / observed['note_id']).exists()
