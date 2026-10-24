"""公式仕様cacheの取得・保存境界。HTTPはfixtureで置換する。"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_note_official_specs as cache


def source():
    return dict(key="fixture", title="公式fixture", category="editor", url="https://www.help-note.com/hc/ja/articles/123")


def invoke(tmp_path, monkeypatch, sources, *flags):
    manifest = tmp_path / "sources.json"
    manifest.write_text(json.dumps({"sources": sources}))
    monkeypatch.setattr(sys, "argv", ["cache", "--manifest", str(manifest), "--output-dir", str(tmp_path / "cache"), "--json", *flags])
    return cache.main()


def test_http_is_opt_in_and_creates_no_files(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cache, "fetch", lambda *a: pytest.fail("HTTP must require opt-in"))
    assert invoke(tmp_path, monkeypatch, [source()]) == 0
    assert not (tmp_path / "cache").exists()
    assert json.loads(capsys.readouterr().out)["mode"] == "dry-run"


def test_external_cache_write_and_hash_readback(tmp_path, monkeypatch, capsys):
    body = b"<h1>fixture</h1><p>official fixture</p>"
    monkeypatch.setattr(cache, "fetch", lambda *a: body)
    assert invoke(tmp_path, monkeypatch, [source()], "--allow-public-http") == 0
    result = json.loads(capsys.readouterr().out)
    entry = result["sources"][0]
    assert Path(entry["html"]).read_bytes() == body
    assert entry["html_sha256"] == hashlib.sha256(body).hexdigest()
    assert entry["markdown_sha256"] == hashlib.sha256(Path(entry["markdown"]).read_bytes()).hexdigest()


@pytest.mark.parametrize("bad", [None, {}, [None], [dict(source(), key="../escape")], [dict(source(), url="file:///tmp/private")], [dict(source(), url="https://example.com/")], [source(), source()]])
def test_invalid_manifest_blocks_before_http_or_write(tmp_path, monkeypatch, bad):
    monkeypatch.setattr(cache, "fetch", lambda *a: pytest.fail("invalid source must block"))
    with pytest.raises(ValueError):
        invoke(tmp_path, monkeypatch, bad, "--allow-public-http")
    assert not (tmp_path / "cache").exists()


def test_package_cache_is_rejected_before_http(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "ROOT", tmp_path)
    monkeypatch.setattr(cache, "fetch", lambda *a: pytest.fail("package cache must block"))
    with pytest.raises(ValueError, match="package"):
        invoke(tmp_path, monkeypatch, [source()], "--allow-public-http")
    assert not (tmp_path / "cache").exists()


def test_output_symlink_escape_is_rejected_before_http(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    output = tmp_path / "cache"
    output.mkdir()
    (output / "html").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(cache, "fetch", lambda *a: pytest.fail("symlink escape must block"))
    with pytest.raises(ValueError, match="symlink"):
        invoke(tmp_path, monkeypatch, [source()], "--allow-public-http")
    assert list(outside.iterdir()) == []


def test_redirect_to_unapproved_host_is_blocked():
    with pytest.raises(ValueError, match="公式"):
        cache.OfficialRedirectHandler().redirect_request(None, None, 302, "", {}, "https://example.com/")
