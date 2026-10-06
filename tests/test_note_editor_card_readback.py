import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "note_editor_apply.py"
SPEC = importlib.util.spec_from_file_location("note_editor_apply_card_readback", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_card_state_requires_exact_single_embedded_figure():
    state = {
        "url": "https://editor.note.com/notes/nabc123/edit/",
        "figures": 1,
        "services": ["note"],
        "raw_paragraphs": 0,
        "ordinary_links": 0,
    }
    assert MODULE.card_state_ok(state, "nabc123")
    assert not MODULE.card_state_ok({**state, "figures": 2}, "nabc123")
    assert not MODULE.card_state_ok({**state, "ordinary_links": 1}, "nabc123")
    assert not MODULE.card_state_ok({**state, "raw_paragraphs": 1}, "nabc123")
    assert not MODULE.card_state_ok(state, "nother")


def test_card_readback_waits_for_async_conversion(monkeypatch):
    pending = {
        "url": "https://editor.note.com/notes/nabc123/edit/",
        "figures": 0,
        "raw_paragraphs": 1,
        "ordinary_links": 0,
    }
    converted = {**pending, "figures": 1, "services": ["note"], "raw_paragraphs": 0}
    samples = iter([pending, converted])
    monkeypatch.setattr(MODULE, "read_card_state", lambda *_: next(samples))
    monkeypatch.setattr(MODULE.time, "sleep", lambda *_: None)
    receipt = MODULE.verify_card_after_enter("orca", "page", "https://note.com/x", "nabc123")
    assert receipt["status"] == "ok"
    assert receipt["samples"] == 2


def test_card_readback_stops_on_wrong_note(monkeypatch):
    monkeypatch.setattr(
        MODULE,
        "read_card_state",
        lambda *_: {"url": "https://editor.note.com/notes/nother/edit/", "figures": 1},
    )
    receipt = MODULE.verify_card_after_enter("orca", "page", "https://note.com/x", "nabc123")
    assert receipt["status"] == "note_identity_mismatch"
    assert receipt["samples"] == 1


def test_card_readback_does_not_reinsert_when_conversion_is_pending(monkeypatch):
    monkeypatch.setattr(
        MODULE,
        "read_card_state",
        lambda *_: {
            "url": "https://editor.note.com/notes/nabc123/edit/",
            "figures": 0,
            "raw_paragraphs": 1,
            "ordinary_links": 0,
        },
    )
    receipt = MODULE.verify_card_after_enter(
        "orca", "page", "https://note.com/x", "nabc123", timeout_seconds=0
    )
    assert receipt["status"] == "conversion_unconfirmed"
    assert receipt["observed"]["raw_paragraphs"] == 1
