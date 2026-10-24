"""記事別履歴の保全と読戻しで、意味の採否と版一致を混同しない。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import nps_script_loader
from note_feedback import article_directory, read_article_feedback, record_feedback


@pytest.fixture
def setup(tmp_path):
    dirs = {name: tmp_path / name for name in ("sources", "drafts", "feedback")}
    for path in dirs.values():
        path.mkdir()
    source = dirs["sources"] / "source.html"
    prior = dirs["sources"] / "prior.html"
    draft = dirs["drafts"] / "draft.html"
    source.write_text("本人の追記", encoding="utf-8")
    prior.write_text("以前の原稿", encoding="utf-8")
    draft.write_text("本人の追記。採用した修正", encoding="utf-8")
    entries = [{"origin": "author", "decision": "source_preserved", "before": "", "after": "本人の追記",
                "reason": "現在の本人原稿を優先", "evidence_ref": "fixture://author"}]
    return dirs, source, draft, prior, entries


def record(setup):
    dirs, source, draft, prior, entries = setup
    return record_feedback(dirs, "article", source, draft, prior, entries, conversation_id="current")


def test_saved_readback_and_history(setup):
    before = record(setup)
    dirs, source, draft, prior, entries = setup
    assert read_article_feedback(dirs, "article", source, draft) == before
    old = (dirs["feedback"] / "article/feedback.json").read_bytes()
    entries.append({"origin": "ai", "decision": "rejected", "before": "本人の追記", "after": "削った案",
                    "reason": "原文を維持", "evidence_ref": "fixture://user"})
    after = record(setup)
    assert after != before
    history = list((dirs["feedback"] / "article/history").glob("*.json"))
    assert history and history[0].read_bytes() == old
    assert source.read_text() == "本人の追記"


@pytest.mark.parametrize("target", ["source", "draft", "diff", "snapshot", "record_article"])
def test_stale_or_tampered_feedback_stops(setup, target):
    record(setup)
    dirs, source, draft, _, _ = setup
    base = dirs["feedback"] / "article"
    if target == "source":
        source.write_text("別の原文")
    elif target == "draft":
        draft.write_text("新しい本人追記")
    elif target == "diff":
        (base / "note-vs-local-diff.md").write_text("差分を省略")
    elif target == "snapshot":
        next((base / "snapshots").glob("*.txt")).write_text("改変")
    else:
        data = json.loads((base / "feedback.json").read_text())
        data["article_id"] = "other"
        (base / "feedback.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_article_feedback(dirs, "article", source, draft)


@pytest.mark.parametrize("article", ["..", "../article", "a/b", "a\\b", ""])
def test_article_path_cannot_escape(setup, article):
    with pytest.raises(ValueError):
        article_directory(setup[0], article)


def test_ai_cannot_be_labeled_author_source(setup):
    setup[4][0]["origin"] = "ai"
    with pytest.raises(ValueError):
        record(setup)


def test_missing_feedback_stops(setup):
    dirs, source, draft, _, _ = setup
    with pytest.raises(FileNotFoundError):
        read_article_feedback(dirs, "article", source, draft)


def test_source_outside_config_stops_before_writing(setup, tmp_path):
    dirs, _, draft, prior, entries = setup
    outside = tmp_path / "outside.html"
    outside.write_text("本人原文")
    with pytest.raises(ValueError):
        record_feedback(dirs, "article", outside, draft, prior, entries, conversation_id="current")
    assert not (dirs["feedback"] / "article").exists()


@pytest.mark.parametrize("name", ["snapshots", "history", "feedback.json", "note-vs-local-diff.md"])
def test_internal_symlink_escape_stops(setup, tmp_path, name):
    dirs, _, _, _, _ = setup
    base = dirs["feedback"] / "article"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside if name in {"snapshots", "history"} else outside / "missing.txt"
    (base / name).symlink_to(target)
    with pytest.raises(ValueError):
        record(setup)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("field,value", [("recorded_at", None), ("recorded_at", []),
                                        ("origin", []), ("decision", {})])
def test_invalid_fields_raise_validation_error(setup, field, value):
    record(setup)
    dirs, source, draft, _, _ = setup
    path = dirs["feedback"] / "article/feedback.json"
    data = json.loads(path.read_text())
    if field == "recorded_at":
        data[field] = value
    else:
        data["entries"][0][field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_article_feedback(dirs, "article", source, draft)


@pytest.fixture
def readback_setup(setup, tmp_path):
    dirs, source, draft, prior, entries = setup
    default = tmp_path / "default-style.md"
    article_style = tmp_path / "article-style.md"
    default.write_text("Generic default style", encoding="utf-8")
    article_style.write_text("Generic article style", encoding="utf-8")
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({
        "schema_version": "nps-workspace-settings/v1", "workspace_root": ".",
        "storage": {key: str(path) for key, path in dirs.items()},
        "style": {"default_profile": str(default), "article_profiles": {"article": [str(article_style)]}},
    }), encoding="utf-8")
    record(setup)
    return settings, default, article_style


def cli(monkeypatch, capsys, settings, source, draft, *extra):
    note_feedback = nps_script_loader.load_script("note_feedback")
    monkeypatch.setattr(sys, "argv", ["note_feedback", "--settings", str(settings),
                                     "--article-id", "article", "--source", str(source),
                                     "--draft", str(draft), *extra])
    code = note_feedback.main()
    return code, json.loads(capsys.readouterr().out)


def test_readback_reads_latest_style_and_all_decisions_without_writes(setup, readback_setup, monkeypatch, capsys):
    dirs, source, draft, _, entries = setup
    settings, default, article_style = readback_setup
    default.write_text("Fresh default style", encoding="utf-8")
    article_style.write_text("Fresh article style", encoding="utf-8")
    for decision in ("rejected", "pending", "adopted"):
        entries.append({"origin": "author", "decision": decision, "before": "old", "after": "new",
                        "reason": "Latest human feedback " + decision, "evidence_ref": "fixture://latest"})
    record(setup)
    before = {p: p.read_bytes() for p in settings.parent.rglob("*") if p.is_file()}
    code, result = cli(monkeypatch, capsys, settings, source, draft, "--readback")
    assert code == 0 and result["status"] == "readback"
    assert [ref["content"] for ref in result["style_references"]] == ["Fresh default style", "Fresh article style"]
    assert result["feedback"]["record"]["entries"] == entries
    assert result["feedback"]["diff"]["content"] == (dirs["feedback"] / "article/note-vs-local-diff.md").read_text()
    for key, path in (("source", source), ("draft", draft)):
        assert result[key]["path"] == str(path.resolve())
        assert result[key]["sha256"] == result["feedback_readback"]["snapshot_hashes"][key]
        assert result[key]["content"] == path.read_text()
    assert result["semantic_understanding_verified"] is False
    assert result["human_adoption_verified"] is False
    assert result["publication_allowed"] is False
    assert {p: p.read_bytes() for p in settings.parent.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("target", ["missing", "record", "snapshot", "diff"])
def test_readback_blocks_missing_or_tampered_history(setup, readback_setup, monkeypatch, capsys, target):
    dirs, source, draft, _, _ = setup
    base = dirs["feedback"] / "article"
    if target == "missing":
        (base / "feedback.json").unlink()
    elif target == "record":
        (base / "feedback.json").write_text("{}")
    elif target == "snapshot":
        next((base / "snapshots").glob("*.txt")).write_text("tampered")
    else:
        (base / "note-vs-local-diff.md").write_text("tampered")
    code, result = cli(monkeypatch, capsys, readback_setup[0], source, draft, "--readback")
    assert code == 1 and result["status"] == "blocked"


@pytest.mark.parametrize("field", ["--prior-draft", "--entries", "--conversation-id"])
def test_readback_rejects_write_fields(setup, readback_setup, monkeypatch, capsys, field):
    with pytest.raises(SystemExit) as exc:
        cli(monkeypatch, capsys, readback_setup[0], setup[1], setup[2], "--readback", field, "unused")
    assert exc.value.code == 2


def test_write_cli_remains_compatible(setup, readback_setup, monkeypatch, capsys, tmp_path):
    _, source, draft, prior, entries = setup
    path = tmp_path / "entries.json"
    path.write_text(json.dumps(entries))
    code, result = cli(monkeypatch, capsys, readback_setup[0], source, draft,
                       "--prior-draft", str(prior), "--entries", str(path), "--conversation-id", "current")
    assert code == 0 and result["status"] == "recorded"


def test_readback_blocks_style_drift_after_validation(setup, readback_setup, monkeypatch, capsys):
    note_workflow_gate = nps_script_loader.load_script("note_workflow_gate")
    original = note_workflow_gate.read_workspace_settings
    def changing_settings(*args):
        result = original(*args)
        readback_setup[1].write_text("changed during validation")
        return result
    monkeypatch.setattr(note_workflow_gate, "read_workspace_settings", changing_settings)
    code, result = cli(monkeypatch, capsys, readback_setup[0], setup[1], setup[2], "--readback")
    assert code == 1 and result["status"] == "blocked"


def test_readback_blocks_history_drift_after_validation(setup, readback_setup, monkeypatch, capsys):
    note_feedback = nps_script_loader.load_script("note_feedback")
    original = note_feedback.read_article_feedback
    def changing_feedback(*args):
        result = original(*args)
        path = setup[0]["feedback"] / "article/feedback.json"
        data = json.loads(path.read_text())
        data["entries"][0]["reason"] = "changed during validation"
        path.write_text(json.dumps(data))
        return result
    monkeypatch.setattr(note_feedback, "read_article_feedback", changing_feedback)
    code, result = cli(monkeypatch, capsys, readback_setup[0], setup[1], setup[2], "--readback")
    assert code == 1 and result["status"] == "blocked"


def test_readback_blocks_source_outside_storage(setup, readback_setup, monkeypatch, capsys, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(setup[1].read_bytes())
    code, result = cli(monkeypatch, capsys, readback_setup[0], outside, setup[2], "--readback")
    assert code == 1 and result["status"] == "blocked"


def test_readback_blocks_non_utf8_style(setup, readback_setup, monkeypatch, capsys):
    readback_setup[1].write_bytes(b"\xff")
    code, result = cli(monkeypatch, capsys, readback_setup[0], setup[1], setup[2], "--readback")
    assert code == 1 and result["status"] == "blocked"


@pytest.mark.parametrize("mode", ["readback", "blocked", "write"])
def test_cli_json_preserves_unicode_on_legacy_stdout(setup, readback_setup, tmp_path, mode):
    import os
    import subprocess

    _, source, draft, prior, entries = setup
    settings, default, article_style = readback_setup
    source.write_text("最新の本人原文 📝", encoding="utf-8")
    draft.write_text("最新の本人原稿。仮定を残す 📝", encoding="utf-8")
    default.write_text("共通口調。未発言を足さない 📝", encoding="utf-8")
    article_style.write_text("この記事の本人語彙 📝", encoding="utf-8")
    entries.append({"origin": "author", "decision": "rejected", "before": "最新の本人原文 📝",
                    "after": "書き換え案", "reason": "本人の語彙を保全 📝", "evidence_ref": "fixture://latest"})
    record(setup)
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/note_feedback.py"),
               "--settings", str(settings), "--article-id", "article",
               "--source", str(source), "--draft", str(draft)]
    if mode == "write":
        entries_path = tmp_path / "entries.json"
        entries_path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
        command.extend(["--prior-draft", str(prior), "--entries", str(entries_path),
                        "--conversation-id", "current"])
    else:
        command.append("--readback")
    if mode == "blocked":
        draft.write_text("現在の原稿が履歴と不一致 📝", encoding="utf-8")
    result = subprocess.run(command, env={**os.environ, "PYTHONIOENCODING": "cp1252"},
                            capture_output=True, check=False)
    assert result.returncode == (1 if mode == "blocked" else 0), result.stderr.decode("cp1252")
    assert result.stderr == b""
    output = json.loads(result.stdout.decode("ascii"))
    assert output["status"] == {"readback": "readback", "blocked": "blocked", "write": "recorded"}[mode]
    if mode == "readback":
        assert output["source"]["content"] == source.read_text(encoding="utf-8")
        assert output["draft"]["content"] == draft.read_text(encoding="utf-8")
        assert [ref["content"] for ref in output["style_references"]] == [
            default.read_text(encoding="utf-8"), article_style.read_text(encoding="utf-8")]
        assert output["feedback"]["record"]["entries"] == entries
    elif mode == "blocked":
        assert output["reason"] == "履歴が現在の原資料・原稿と一致しません"
    else:
        assert output["feedback_readback"] == read_article_feedback(setup[0], "article", source, draft)
