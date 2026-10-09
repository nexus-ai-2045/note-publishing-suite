"""記事版の明示台帳・書込み境界と既存transactionとの整合。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import note_article_version as version
from post_publish import transaction_path


def run(monkeypatch, ledger, *flags):
    monkeypatch.setattr(sys, "argv", ["version", "--note-id", "nfixture", "--ledger", str(ledger), *flags, "prepare", "--reason", "fixture"])
    return version.main()


def test_default_is_dry_run(tmp_path, monkeypatch, capsys):
    ledger = tmp_path / "published_notes.json"
    before = '[{"note_id":"nfixture","title":"fixture"}]'
    ledger.write_text(before)
    assert run(monkeypatch, ledger) == 0
    assert ledger.read_text() == before
    assert json.loads(capsys.readouterr().out)["pending_version"] == "v0.1.1"


def test_explicit_write_uses_shared_lock_and_atomic_writer(tmp_path, monkeypatch):
    ledger = tmp_path / "published_notes.json"
    ledger.write_text('[{"note_id":"nfixture","title":"fixture"}]')
    assert run(monkeypatch, ledger, "--write-ledger") == 0
    assert json.loads(ledger.read_text())[0]["pending_version"] == "v0.1.1"


def test_no_implicit_ledger_search(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["version", "--note-id", "nfixture", "prepare", "--reason", "fixture"])
    with pytest.raises(SystemExit) as exc:
        version.main()
    assert exc.value.code == 2


def test_pending_publication_transaction_blocks(tmp_path, monkeypatch):
    ledger = tmp_path / "published_notes.json"
    ledger.write_text('[{"note_id":"nfixture","title":"fixture"}]')
    transaction_path(ledger).write_text('{}')
    with pytest.raises(ValueError, match="transaction"):
        run(monkeypatch, ledger, "--write-ledger")
    assert "pending_version" not in ledger.read_text()


def test_package_ledger_is_rejected_before_write(tmp_path, monkeypatch):
    monkeypatch.setattr(version, "ROOT", tmp_path)
    ledger = tmp_path / "published_notes.json"
    before = '[{"note_id":"nfixture","title":"fixture"}]'
    ledger.write_text(before)
    with pytest.raises(ValueError, match="package"):
        run(monkeypatch, ledger, "--write-ledger")
    assert ledger.read_text() == before


def test_shared_ledger_lock_rejects_concurrent_version_write(tmp_path, monkeypatch):
    ledger = tmp_path / "published_notes.json"
    before = '[{"note_id":"nfixture","title":"fixture"}]'
    ledger.write_text(before)
    with version.ledger_file_lock(ledger):
        with pytest.raises(RuntimeError, match="別process"):
            run(monkeypatch, ledger, "--write-ledger")
    assert ledger.read_text() == before
