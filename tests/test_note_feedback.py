"""記事別履歴の保全と読戻しで、意味の採否と版一致を混同しない。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
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
