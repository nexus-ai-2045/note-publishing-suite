"""検索候補の取得と、通信・原稿保護の境界を検証する。"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import Mock
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/note_fact_check.py"
SPEC = importlib.util.spec_from_file_location("note_fact_check_search", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    forbidden = Mock(side_effect=AssertionError("テストで実通信は禁止"))
    monkeypatch.setattr(checker, "build_opener", forbidden)
    return forbidden


@pytest.fixture
def draft(tmp_path):
    path = tmp_path / "draft.md"
    path.write_text("未確認の2026年の数値。非公開の原稿本文。", encoding="utf-8")
    return path


def invoke(monkeypatch, capsys, draft, *options):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "local", str(draft), "--json", *options])
    code = checker.main()
    return code, json.loads(capsys.readouterr().out)


def mock_response(monkeypatch, payload):
    opener = Mock()
    opener.open.return_value = io.BytesIO(json.dumps(payload).encode())
    factory = Mock(return_value=opener)
    monkeypatch.setattr(checker, "build_opener", factory)
    return factory, opener


def test_default_local_never_opens_network(monkeypatch, capsys, draft, deny_network):
    before = draft.read_bytes()
    code, result = invoke(monkeypatch, capsys, draft)
    assert code == 0
    assert result["finding_count"] > 0
    assert "search_results" not in result
    assert draft.read_bytes() == before
    deny_network.assert_not_called()


def test_dry_run_never_opens_network_or_creates_report(
    monkeypatch, capsys, draft, tmp_path, deny_network
):
    report = tmp_path / "new-directory" / "report.json"
    code, result = invoke(
        monkeypatch, capsys, draft, "--search-query", "公開検索語",
        "--dry-run", "--report-path", str(report),
    )
    assert code == 0
    assert result["search_queries"] == ["公開検索語"]
    assert result["search_results"] == []
    assert result["dry_run"] is True
    assert not report.parent.exists()
    deny_network.assert_not_called()


def test_success_candidates_stay_unverified_and_only_query_is_sent(
    monkeypatch, capsys, draft, tmp_path
):
    factory, opener = mock_response(monkeypatch, {
        "results": [{"url": "https://example.org/source", "title": "出典", "content": "要旨"}],
        "unresponsive_engines": [],
    })
    report = tmp_path / "report.json"
    code, result = invoke(
        monkeypatch, capsys, draft, "--search-query", "公開検索語",
        "--report-path", str(report),
    )
    assert code == 0
    assert result["verification"] == "unverified"
    assert result["publication"] == "disabled"
    search = result["search_results"][0]
    assert search["status"] == "ok"
    assert search["verification"] == "unverified"
    assert search["candidates"][0]["verification"] == "unverified"
    assert search["candidates"][0]["body_status"] == "not_fetched"
    assert json.loads(report.read_text()) == result
    opener.open.assert_called_once()
    request = opener.open.call_args.args[0]
    assert parse_qs(urlsplit(request.full_url).query) == {
        "q": ["公開検索語"], "format": ["json"], "language": ["ja-JP"],
    }
    assert request.data is None
    handlers = factory.call_args.args
    assert any(isinstance(h, ProxyHandler) and h.proxies == {} for h in handlers)
    assert any(isinstance(h, checker.NoRedirect) for h in handlers)


@pytest.mark.parametrize(("payload", "status", "exit_code"), [
    ({"results": []}, "no_results", 0),
    ({"results": [], "unresponsive_engines": [["google", "CAPTCHA"]]}, "unavailable", 2),
    ({"results": [{"url": "https://example.org"}],
      "unresponsive_engines": [["google", "timeout"]]}, "partial", 0),
])
def test_empty_captcha_and_partial_results_are_distinct(
    monkeypatch, capsys, draft, payload, status, exit_code
):
    mock_response(monkeypatch, payload)
    code, result = invoke(monkeypatch, capsys, draft, "--search-query", "検索")
    search = result["search_results"][0]
    assert code == exit_code
    assert search["status"] == status
    assert search["unresponsive_engines"] == payload.get("unresponsive_engines", [])


def test_network_failure_is_error(monkeypatch, capsys, draft):
    opener = Mock()
    opener.open.side_effect = URLError("connection refused")
    monkeypatch.setattr(checker, "build_opener", Mock(return_value=opener))
    code, result = invoke(monkeypatch, capsys, draft, "--search-query", "検索")
    assert code == 2
    assert result["search_results"][0]["status"] == "error"
    assert "connection refused" in result["search_results"][0]["error"]


@pytest.mark.parametrize("endpoint", [
    "https://example.com", "http://example.com", "http://localhost:8888",
    "http://127.0.0.2:8888", "http://127.0.0.1.evil.example:8888",
    "http://user@127.0.0.1:8888", "http://127.0.0.1:8888/path",
    "http://127.0.0.1:8888/?q=secret", "http://127.0.0.1:8888/#fragment",
    "http://127.0.0.1:99999",
])
def test_invalid_endpoint_rejected_before_network(
    monkeypatch, capsys, draft, deny_network, endpoint
):
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, capsys, draft, "--endpoint", endpoint, "--search-query", "検索")
    assert error.value.code == 2
    deny_network.assert_not_called()


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_handler_never_creates_redirect_request(status):
    handler = checker.NoRedirect()
    assert isinstance(handler, HTTPRedirectHandler)
    assert handler.redirect_request(
        None, None, status, "redirect", {}, "https://example.com/leak"
    ) is None


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_report_cannot_overwrite_draft(
    monkeypatch, capsys, draft, tmp_path, deny_network, alias
):
    report = draft
    if alias != "same":
        report = tmp_path / "report.json"
        if alias == "symlink":
            report.symlink_to(draft)
        else:
            report.hardlink_to(draft)
    before = draft.read_bytes()
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, capsys, draft, "--report-path", str(report), "--search-query", "検索")
    assert error.value.code == 2
    assert draft.read_bytes() == before
    deny_network.assert_not_called()


@pytest.mark.parametrize("payload", [[], {}, {"results": "invalid"}, {"results": [None]}])
def test_invalid_responses_are_errors(monkeypatch, payload):
    mock_response(monkeypatch, payload)
    result = checker.search_sources("検索", "http://127.0.0.1:8888", 5)
    assert result["status"] == "error"
    assert "error" in result
