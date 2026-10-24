from pathlib import Path
import hashlib
import json
import importlib.util
import pytest
_spec = importlib.util.spec_from_file_location("workflow_fixture", Path(__file__).with_name("test_note_workflow_gate.py"))
_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixture)
gate, packet, approve = _fixture.gate, _fixture.packet, _fixture.approve

ROOT = Path(__file__).resolve().parents[1]

def receipt_for(text, article="article", conversation="current"):
    from pre_publish_check import split_frontmatter
    body = split_frontmatter(text)[1]
    return dict(schema_version="nps-prepublish-review/v1", article_id=article,
                conversation_id=conversation, actor="user", status="review_required",
                draft_sha256=hashlib.sha256(text.encode()).hexdigest(),
                body_sha256=hashlib.sha256(body.encode()).hexdigest(),
                issue_codes=["missing_early_takeaway"], reason="本人が構成保持を採用",
                evidence_ref="runtime://synthetic-fixture-only", observed_at="2026-10-06T18:00:00+09:00")

def attach_review(packet, tmp_path):
    path = tmp_path / "editorial.json"
    path.write_text(json.dumps(receipt_for(Path(packet["draft"]).read_text())))
    packet["prepublish_review_receipt"] = str(path)
    return path

def test_workflow_review_remains_manual(packet, tmp_path):
    attach_review(packet, tmp_path)
    result = approve(packet, "publish")
    assert result["status"] == "approved"
    assert result["editorial_review"] == "review_required"
    assert result["manual_publish_required"] is True
    assert result["automation_allowed"] is False

@pytest.mark.parametrize("field", ["article_id", "conversation_id", "draft_sha256", "body_sha256", "actor"])
def test_workflow_rejects_mismatched_review(packet, tmp_path, field):
    path = attach_review(packet, tmp_path)
    data = json.loads(path.read_text()); data[field] = "other"
    path.write_text(json.dumps(data))
    assert approve(packet, "publish")["status"] == "blocked"

def test_changed_review_invalidates_workflow_approval(packet, tmp_path):
    path = attach_review(packet, tmp_path)
    assert approve(packet, "publish")["status"] == "approved"
    data = json.loads(path.read_text()); data["reason"] = "別の採用理由"
    path.write_text(json.dumps(data))
    assert gate.check_packet(packet, "publish", "current")["status"] == "blocked"

def load_review():
    spec = importlib.util.spec_from_file_location("editorial_review_test", ROOT / "scripts/review_draft.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def test_review_card_keeps_review_state(tmp_path):
    draft = tmp_path / "draft.md"
    text = "---\narticle_lane: exploratory_draft\n---\n# 記事\n\n" + "これは本文です。" * 60
    draft.write_text(text)
    path = tmp_path / "review.json"; path.write_text(json.dumps(receipt_for(text)))
    card = load_review().build_context_card(draft, prepublish_review_receipt=path,
                                          article_id="article", conversation_id="current")
    assert card["prepublish"]["overall"] == "review_required"
    assert card["external_actions_performed"] == []

def test_other_error_blocks_review(tmp_path):
    draft = tmp_path / "draft.md"; text = "---\narticle_lane: exploratory_draft\n---\n# 記事\n\n" + "sk-" + "x" * 30
    draft.write_text(text); path = tmp_path / "review.json"; path.write_text(json.dumps(receipt_for(text)))
    result = load_review().review_draft(draft, prepublish_review_receipt=path,
                                       article_id="article", conversation_id="current")
    assert result["verdict"] == "blocked"
    assert "prepublish_error_secret_like_value" in result["reason_codes"]
