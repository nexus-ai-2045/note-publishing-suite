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
        diagnostics=True,
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


def test_source_linebreaks_keep_semantic_paragraphs(nvp):
    body = "最初の文。\n[出典](https://example.com/source)を読む。\n続く文。\n\n次の話題。\nその続き。\n"
    output = nvp.md_body_to_note_html(body, {})
    assert output == (
        '<p>最初の文。<br><a href="https://example.com/source" target="_blank" '
        'rel="noopener nofollow">出典</a>を読む。<br>続く文。</p>\n'
        '<p>次の話題。<br>その続き。</p>'
    )


def test_soft_break_group_stops_at_special_blocks(nvp):
    body = (
        "前半。\n続き。\n## 見出し\n- 項目\n1. 番号\n"
        "（図: 図解）\nhttps://example.com/article\n"
        "後半。\n終わり。\n"
    )
    output = nvp.md_body_to_note_html(body, {})
    assert output.startswith('<p>前半。<br>続き。</p>\n<h2>見出し</h2>')
    assert '<ul><li>項目</li></ul>' in output
    assert '<ol><li>番号</li></ol>' in output
    assert 'class="figure-placeholder"' in output
    assert 'class="embed-card"' in output
    assert output.endswith('<p>後半。<br>終わり。</p>')


def test_inline_image_is_preserved_in_soft_break_paragraph(nvp):
    output = nvp.md_body_to_note_html("説明。\n図 ![説明図](image.png) を参照。\n\n次の説明。", {})
    assert output == (
        '<p>説明。<br>図 <img src="image.png" alt="説明図" loading="lazy"> を参照。</p>\n'
        '<p>次の説明。</p>'
    )


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_reading_view_hides_metadata_comments_and_diagnostics(nvp, tmp_path, newline):
    source = newline.join([
        "---", 'title: 読書用', "status: human_review_required", "---",
        "<!-- internal: secret -->", "本文の前半。<!--", "非公開のメモ", "-->本文の後半。",
        "【本人確認待ち】", "---", "続き。",
    ])
    path = tmp_path / "draft.md"
    path.write_text(source, encoding="utf-8")
    output, stats = nvp.render(source, path, TEMPLATE_PATH, CSS_PATH, None)
    for hidden in ("human_review_required", "非公開のメモ", "secret", "字数（", 'class="mock-toolbar"', "生成:"):
        assert hidden not in output
    assert "本文の前半。本文の後半。" in output
    assert "本人確認待ち" in output
    assert "<hr>" in output
    assert path.read_bytes() == source.encode("utf-8")
    assert "warnings" in stats


def test_frontmatter_closing_at_eof_and_unclosed_comment(nvp, tmp_path):
    assert nvp.strip_frontmatter("---\ntitle: 題名\n---") == ""
    output, _ = render_fixture(nvp, tmp_path, "本文。\n<!-- 隠す未完のメモ")
    assert "隠す未完のメモ" not in output
    assert "本文。" in output


def test_alternative_comment_end_preserves_following_body(nvp, tmp_path):
    output, _ = render_fixture(nvp, tmp_path, "前半。\n<!-- 内部 --!>\n後半。")
    assert "後半。" in output
    assert "内部" not in output


def test_empty_or_list_metadata_does_not_crash(nvp, tmp_path):
    source = "---\ntitle: 題名\nseries:\nnotes:\nseries_name_working:\n- 項目\n---\n本文。"
    output, _ = render_fixture(nvp, tmp_path, source)
    assert "本文。" in output
    assert "題名" in output


def test_link_query_and_label_are_escaped_once(nvp, tmp_path):
    import html
    output, _ = render_fixture(nvp, tmp_path, "---\ntitle: リンク検証\n---\n[A&B](https://example.com/?a=1&b=2)")
    href = re.search(r'<a href="([^"]+)"', output).group(1)
    assert html.unescape(href) == "https://example.com/?a=1&b=2"
    assert ">A&amp;B</a>" in output


def test_markdown_images_render_without_becoming_links(nvp, tmp_path):
    body = '# 記事タイトル\n\n![相対画像](inline-1-curve.png)\n\n前 ![遠隔画像](https://example.com/image.png?x=1&y=2) 後 [参照](https://example.com/article)\n'
    output, _ = render_fixture(nvp, tmp_path, body)
    assert '<img src="inline-1-curve.png" alt="相対画像" loading="lazy">' in output
    assert '<img src="https://example.com/image.png?x=1&amp;y=2" alt="遠隔画像" loading="lazy">' in output
    assert output.count('<a href="https://') == 1
    assert '![' not in output
    assert len(nvp.MD_LINK_RE.findall(body)) == 1


def test_image_alt_is_escaped_and_not_processed_as_markup(nvp, tmp_path):
    body = '# 記事タイトル\n\n!["<tag> & **太字** *斜体* `code` 【確認】](image.png)\n'
    output, stats = render_fixture(nvp, tmp_path, body)
    assert 'alt="&quot;&lt;tag&gt; &amp; **太字** *斜体* `code` 【確認】"' in output
    assert '<strong>' not in output
    assert stats['warnings']['italic'] == 0
    assert stats['warnings']['inline_code'] == 0


@pytest.mark.parametrize('target', [
    'javascript:alert', 'data:image/png;base64,abc', 'file:///tmp/image.png',
    '//example.com/image.png', '/image.png', '\\image.png',
    'https://example.com\\image.png', 'https://[invalid/image.png',
])
def test_unsafe_image_sources_remain_literal(nvp, tmp_path, target):
    output, _ = render_fixture(nvp, tmp_path, f'# 記事タイトル\n\n![画像]({target})\n')
    assert '<img ' not in output
    assert '<a href=' not in output
    assert '![画像]' in output


def test_emphasis_can_span_links_while_preserving_image_alt(nvp, tmp_path):
    body = '# 記事タイトル\n\n**[参照](https://example.com/article)**\n\n*前 [参照](https://example.com/article) 後*\n\n![**代替** *説明*](image.png)\n'
    output, stats = render_fixture(nvp, tmp_path, body)
    assert '<strong><a href="https://example.com/article"' in output
    assert 'rel="noopener nofollow">参照</a></strong>' in output
    assert '<em class="warn-inline-italic">前 <a href="https://example.com/article"' in output
    assert 'rel="noopener nofollow">参照</a> 後</em>' in output
    assert 'alt="**代替** *説明*"' in output
    assert stats['warnings']['italic'] == 1


@pytest.mark.parametrize("separator", ["---", "***", "___"])
def test_soft_break_group_stops_at_horizontal_rule(nvp, separator):
    output = nvp.md_body_to_note_html(f"前。\n{separator}\n後。", {})
    assert output == '<p>前。</p>\n<hr>\n<p class="hr-gap">&nbsp;</p>\n<p>後。</p>'


def test_special_prefix_plain_text_does_not_stall(nvp):
    output = nvp.md_body_to_note_html("#通常の文\n---続く文\n| 表ではない |\n次の文", {})
    assert output == '<p>#通常の文<br>---続く文<br>| 表ではない |<br>次の文</p>'


def test_soft_break_group_stops_at_table_and_quote(nvp):
    output = nvp.md_body_to_note_html("前。\n| A | B |\n| --- | --- |\n| 一 | 二 |\n> 引用。\n後。", {})
    assert output.startswith('<p>前。</p>\n<div class="table-warning">')
    assert '<blockquote><p>引用。</p></blockquote>' in output
    assert output.endswith('<p>後。</p>')
