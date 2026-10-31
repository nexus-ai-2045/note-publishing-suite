"""note_preview.py が **…** を太字で出すことを確かめる。"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "note_preview.py"


def load():
    spec = importlib.util.spec_from_file_location("note_preview", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bold_in_list_item_and_link():
    module = load()
    out = module.inline_markdown("**要点の見出し。** と [リンク](https://example.com)")
    assert "<strong>要点の見出し。</strong>" in out
    assert '<a href="https://example.com"' in out
    assert "**" not in out
