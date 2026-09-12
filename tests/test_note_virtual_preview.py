"""note_virtual_preview のレンダリング契約テスト。

`scripts/note_virtual_preview.py`（移植元: nexa-articles の render_note_preview.py v2）が
preview-constraints.md の主要項目を落とさず変換することを、最小 fixture で検証する。
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "note_virtual_preview.py"
TEMPLATE_PATH = ROOT / "assets" / "note-preview" / "template.html"
CSS_PATH = ROOT / "assets" / "note-preview" / "note-textnote-body.extracted.css"


def load_note_virtual_preview_module():
    spec = importlib.util.spec_from_file_location("note_virtual_preview", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # exec_module 前に sys.modules へ登録しないと、モジュール内で自己参照する
    # 型注釈や relative import 相当の解決が壊れる場合がある。
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def nvp():
    return load_note_virtual_preview_module()


def render_fixture(nvp, tmp_path: Path, body_md: str, filename: str = "fixture-draft.md"):
    input_path = tmp_path / filename
    input_path.write_text(body_md, encoding="utf-8")
    html_out, stats = nvp.render(
        body_md,
        input_path,
        template_path=TEMPLATE_PATH,
        css_path=CSS_PATH,
        series_registry_path=None,
    )
    return html_out, stats


def test_h1_is_rounded_to_h2_with_warning(nvp, tmp_path):
    body_md = "# 見出し1\n\n本文の1行目。\n"
    html_out, stats = render_fixture(nvp, tmp_path, body_md)

    assert "<h2>" in html_out
    assert "<h1>" not in html_out
    assert "H1→H2 に丸め" in html_out
    assert stats["warnings"]["heading_rounded"] == 1


def test_link_count_in_html_matches_markdown_link_count(nvp, tmp_path):
    body_md = (
        "## 見出しA\n\n"
        "[リンク1](https://example.com/a) を参照。\n\n"
        "## 見出しB\n\n"
        "[リンク2](https://example.com/b) と [リンク3](https://example.com/c) を参照。\n"
    )
    html_out, _ = render_fixture(nvp, tmp_path, body_md)

    md_link_count = len(nvp.MD_LINK_RE.findall(body_md))
    html_link_count = len(re.findall(r'<a href="https?://', html_out))

    assert md_link_count == 3
    assert html_link_count == md_link_count
    assert 'target="_blank" rel="noopener nofollow"' in html_out


def test_figure_line_renders_placeholder_frame_with_caption(nvp, tmp_path):
    body_md = (
        "## 見出し\n\n"
        "本文。\n\n"
        "（図: 年次推移のグラフ）\n\n"
        "続きの本文。\n"
    )
    html_out, stats = render_fixture(nvp, tmp_path, body_md)

    assert 'class="figure-placeholder"' in html_out
    assert "年次推移のグラフ" in html_out
    assert "対応する指定が見つかりません" in html_out  # .notes.md が無い fixture のため
    assert stats["figure_details_found"] == 0


def test_markdown_table_renders_warning_block(nvp, tmp_path):
    body_md = (
        "## 比較\n\n"
        "| A | B |\n"
        "| --- | --- |\n"
        "| 1 | 2 |\n"
    )
    html_out, stats = render_fixture(nvp, tmp_path, body_md)

    assert 'class="table-warning"' in html_out
    assert "note editor に規則がありません" in html_out
    assert stats["warnings"]["table"] == 1


def test_two_or_more_headings_generate_toc_block(nvp, tmp_path):
    body_md = "## 見出しA\n\n本文A。\n\n## 見出しB\n\n本文B。\n"
    html_out, _ = render_fixture(nvp, tmp_path, body_md)

    assert 'class="toc-block"' in html_out
    toc_match = re.search(r'<div class="toc-block">(.*?)</div>', html_out, re.S)
    assert toc_match is not None
    assert toc_match.group(1).count("<li") == 2


def test_single_heading_does_not_generate_toc_block(nvp, tmp_path):
    body_md = "## 見出しのみ\n\n本文。\n"
    html_out, _ = render_fixture(nvp, tmp_path, body_md)

    assert 'class="toc-block"' not in html_out
