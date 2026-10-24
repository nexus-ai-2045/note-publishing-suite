"""承認済みfixtureでも、失敗後の変更を一切続けない。実記事は操作しない。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import note_editor_apply as editor


@pytest.mark.parametrize("status", ["fail", "manual_boundary", "no_empty_paragraph", "selection_not_empty", "unknown"])
def test_embed_failure_stops_all_following_mutations(tmp_path, monkeypatch, status):
    url = "https://example.com/fixture"
    urls = tmp_path / "urls.json"
    urls.write_text(json.dumps([url, url + "/second"]))
    packet = {"article_id": "nfixture", "settings": {"account": "fixture"},
              "edit_plan": {"urls": [url, url + "/second"], "tags": ["fixture"], "toc": True, "save": True}}
    monkeypatch.setattr(editor, "load_packet", lambda p: packet)
    monkeypatch.setattr(editor, "check_packet", lambda *a, **kw: {"status": "approved"})
    monkeypatch.setattr(editor, "read_page_identity", lambda *a: {"note_id": "nfixture", "url": "https://editor.note.com/notes/nfixture/edit/", "account": "fixture", "account_identity_verified": True, "account_identity_source": "authenticated_account_menu", "account_identity_id": "fixture"})
    calls = []
    monkeypatch.setattr(editor, "embed_url", lambda *a: calls.append("embed") or status)
    monkeypatch.setattr(editor, "insert_toc", lambda *a: calls.append("toc"))
    monkeypatch.setattr(editor, "add_tags", lambda *a: calls.append("tags"))
    monkeypatch.setattr(editor, "click_label", lambda *a: calls.append("save"))
    monkeypatch.setattr(editor, "figures", lambda *a: [])
    monkeypatch.setattr(sys, "argv", ["apply", "--page", "fixture", "--expect-note-id", "nfixture", "--expect-account", "fixture", "--urls-file", str(urls), "--toc", "--tags", "fixture", "--save", "--workflow-packet", str(tmp_path / "packet.json"), "--conversation-id", "fixture", "--nps-settings", str(tmp_path / "settings.json")])
    assert editor.main() == 1
    assert calls == ["embed"]


@pytest.mark.parametrize("identity", [
    {}, {"account_identity_verified": True},
    {"account_identity_verified": True, "account_identity_source": "article_image_alt", "account_identity_id": "fixture"},
    {"account_identity_verified": True, "account_identity_source": "authenticated_account_menu", "account_identity_id": "other"},
])
def test_mutation_preflight_rejects_unproven_current_account(identity):
    observed = {"note_id": "nfixture", "account": "fixture", **identity}
    errors = editor.preflight_errors(observed, {"note_id": "nfixture", "account": "fixture"}, require_verified_account=True)
    assert "authenticated_account_identity_unverified" in errors


def test_generic_dom_identity_does_not_claim_current_account(monkeypatch):
    monkeypatch.setattr(editor, "eval_js", lambda *a: {"account": "fixture", "account_identity_verified": True})
    assert editor.read_page_identity("fixture", "fixture")["account_identity_verified"] is False


@pytest.mark.parametrize("url", ["", "https://example.com/notes/nfixture/edit/", "https://editor.note.com/notes/nother/edit/", "https://editor.note.com/notes/nfixtureevil/edit/"])
def test_mutation_preflight_requires_exact_editor_target(url):
    observed = {"note_id": "nfixture", "url": url, "account": "fixture",
                "account_identity_verified": True, "account_identity_source": "authenticated_account_menu", "account_identity_id": "fixture"}
    assert "editor_target_url_unverified" in editor.preflight_errors(observed, {"note_id": "nfixture", "account": "fixture"}, require_verified_account=True)
