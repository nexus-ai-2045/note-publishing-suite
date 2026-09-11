#!/usr/bin/env python3
"""draft Markdown を「仮想 note」の HTML として表示する変換スクリプト。

移植元: nexa-articles `sources/_tools/note-preview/render_note_preview.py`（v2、2026-09-11 実測）。
移植元は note editor 実物の DOM/CSS 実測
（note-article-dom-analysis.md / editor-dom-analysis.md / editor-js-analysis.md /
preview-constraints.md、いずれも `docs/note-preview/` にコピー）に寄せて、
draft Markdown を note の本物の CSS で見た目確認できる HTML に変換する。

移植で汎用化した点（記事 repo 固有パスの引数化）:
- テンプレート / 抽出 CSS のパスを `--template` / `--css` で上書き可能にした
  （既定値は `assets/note-preview/` 配下、このスクリプトからの相対パス）。
- 移植元がハードコードしていた nexa-articles 固有の
  `series-registry.md`（3階層上の固定パス）参照を `--series-registry`
  （既定 None = 参照しない）に置き換えた。指定しない場合、シリーズ名は
  frontmatter の `series_name_working` またはシリーズ ID そのものを使う
  （nexa-articles 固有のシリーズ ID → 話数上限のフォールバック表は移植していない）。
- 挿絵指定（`.notes.md` の「挿絵」節）・TOP 画像案（`<name>-production-pack.md` の
  「TOP 画像」節）の読み込みは、入力ファイルからの相対探索のためそのまま移植した。

Usage:
    python3 scripts/note_virtual_preview.py <input.md> [-o output.html]
    python3 scripts/note_virtual_preview.py <input.md> --template PATH --css PATH --series-registry PATH
"""

import argparse
import datetime
import html
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_TEMPLATE_PATH = REPO_ROOT / "assets" / "note-preview" / "template.html"
DEFAULT_CSS_PATH = REPO_ROOT / "assets" / "note-preview" / "note-textnote-body.extracted.css"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
BARE_URL_LINE_RE = re.compile(r"^\s*(https?://\S+)\s*$")
FIGURE_LINE_RE = re.compile(r"^\s*（図[:：]\s*(.+?)\s*）\s*$")
TODO_MARKER_RE = re.compile(r"【([^】]*)】")
# 「（本人の判定をここに置く）」のような本人記入プレースホルダ（【】以外の形）
PLACEHOLDER_PAREN_RE = re.compile(r"（[^（）]*本人[^（）]*(?:判定|記入|確認)[^（）]*(?:置く|欄)[^（）]*）")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
# ** で囲まれた太字は bold_markdown 側で先に消費するため、ここでは残った単独 * のみを拾う
ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)")

WARNINGS = {
    "inline_code": 0,
    "italic": 0,
    "table": 0,
    "heading_rounded": 0,
}


def reset_warnings() -> None:
    for k in WARNINGS:
        WARNINGS[k] = 0


# ---------------------------------------------------------------------------
# frontmatter / series header
# ---------------------------------------------------------------------------

def parse_frontmatter(md_text: str) -> dict:
    """先頭の YAML frontmatter を簡易パースする（依存追加を避けるための最小実装）。"""
    m = FRONTMATTER_RE.match(md_text)
    if not m:
        return {}
    raw = m.group(1)
    meta: dict = {}
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith(" ") or line.startswith("-"):
            # リストや sources: の子要素はここでは無視（このツールで使わない）
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value:
            meta[key] = value
    return meta


def strip_frontmatter(md_text: str) -> str:
    m = FRONTMATTER_RE.match(md_text)
    if not m:
        return md_text
    return md_text[m.end():]


def lookup_series_registry(series_registry_path: Optional[Path]) -> dict:
    """series-registry 相当の表からシリーズ名を拾う（表の2列目、簡易パース）。

    `--series-registry` で明示指定されたファイルのみを読む（既定 None = 参照しない）。
    """
    names: dict = {}
    if series_registry_path is None or not series_registry_path.exists():
        return names
    text = series_registry_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        series_id, series_name = cells[0], cells[1]
        if series_id in ("ID", "---") or series_id.startswith("-"):
            continue
        if series_id:
            names[series_id] = series_name
    return names


def build_series_header(meta: dict, series_registry_path: Optional[Path]) -> str:
    """frontmatter と（あれば）series-registry からシリーズヘッダーを組む。"""
    series = meta.get("series", "").strip()
    episode = meta.get("episode", "").strip()
    series_total = meta.get("series_total", "").strip()
    publish_plan = meta.get("publish_plan", "").strip()
    period = meta.get("period", "").strip()
    series_name_working = meta.get("series_name_working", "").strip()

    if not series:
        return ""

    registry_names = lookup_series_registry(series_registry_path)
    series_name = registry_names.get(series, series_name_working or series)

    if series_total:
        label = f"{series_name}｜第{episode or '?'}話／全{series_total}話"
    elif period:
        label = f"{series_name}｜第{episode or '?'}回（{period}）"
    else:
        label = f"{series_name}｜第{episode or '?'}話"

    if publish_plan:
        plan_line = f'<div class="series-meta">公開予定: {html.escape(publish_plan)}</div>'
    else:
        plan_line = '<div class="series-meta">公開予定: 未定</div>'

    return (
        f'<span class="series-pill">{html.escape(label)}</span>'
        f'{plan_line}'
    )


# ---------------------------------------------------------------------------
# 字数カウント（本文のみ、リンクURL・図を除く）
# ---------------------------------------------------------------------------

def _strip_countable(stripped: str) -> Optional[str]:
    """本文1行を字数カウント対象に整形する。カウント対象外の行は None を返す。"""
    if not stripped:
        return None
    if FIGURE_LINE_RE.match(stripped):
        return None
    if BARE_URL_LINE_RE.match(stripped):
        return None
    if stripped in ("---", "***", "___", "参考"):
        return None

    def _link_text(m: "re.Match[str]") -> str:
        return m.group(1)

    return MD_LINK_RE.sub(_link_text, stripped)


def count_body_characters(md_text: str) -> int:
    """本文の文字数を数える。frontmatter・URL・図行・見出し記号・空行を除く簡易カウント。"""
    body = strip_frontmatter(md_text)
    total = 0
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        counted = _strip_countable(stripped)
        if counted is None:
            continue
        total += len(counted)
    return total


# ---------------------------------------------------------------------------
# アウトライン（H2/H3 と、直属テキストの字数）
# ---------------------------------------------------------------------------

def build_outline(body_md: str) -> List[dict]:
    lines = body_md.splitlines()
    headings: List[dict] = []
    for idx, line in enumerate(lines):
        s = line.strip()
        if s.startswith("### "):
            headings.append({"level": 3, "text": s[4:].strip(), "idx": idx, "rounded": False})
        elif s.startswith("## "):
            headings.append({"level": 2, "text": s[3:].strip(), "idx": idx, "rounded": False})
        elif s.startswith("# ") and not s.startswith("## "):
            headings.append({"level": 2, "text": s[2:].strip(), "idx": idx, "rounded": True})

    for i, h in enumerate(headings):
        start = h["idx"] + 1
        end = headings[i + 1]["idx"] if i + 1 < len(headings) else len(lines)
        count = 0
        for line in lines[start:end]:
            counted = _strip_countable(line.strip())
            if counted is None:
                continue
            count += len(counted)
        h["char_count"] = count
    return headings


def render_outline_html(headings: List[dict]) -> str:
    if not headings:
        return ""
    items = []
    for h in headings:
        label = html.escape(h["text"])
        rounded = ' <span class="outline-rounded">（H1→H2 丸め）</span>' if h.get("rounded") else ""
        cls = ' class="outline-h3"' if h["level"] == 3 else ""
        items.append(
            f'<li{cls}>{label}{rounded} '
            f'<span class="outline-count">（約{h["char_count"]:,}字）</span></li>'
        )
    return (
        '<div class="outline-panel">'
        '<div class="outline-panel__title">アウトライン（H2/H3・節の字数）</div>'
        f'<ol>{"".join(items)}</ol>'
        '</div>'
    )


# ---------------------------------------------------------------------------
# .notes.md の「挿絵」節 / production pack の「TOP 画像」節パース
# ---------------------------------------------------------------------------

FIGURE_HEADING_RE = re.compile(r"^###\s*図\s*(\d+)\s*(.*)$")
TOP_IMAGE_HEADING_RE = re.compile(r"^###\s*案\s*(\d+)\s*(.*)$")
BULLET_FIELD_RE = re.compile(r"^-\s*\*{0,2}([^*：:]+?)\*{0,2}\s*[：:]\s*(.+)$")


def find_notes_path(input_path: Path, meta: dict) -> Optional[Path]:
    notes_rel = meta.get("notes", "").strip()
    if notes_rel:
        candidate = (input_path.parent / notes_rel).resolve()
        if candidate.exists():
            return candidate
    # 既定: <name>.md -> <name>.notes.md（拡張子を .notes.md に差し替え）
    candidate = input_path.parent / (input_path.stem + ".notes.md")
    if candidate.exists():
        return candidate
    return None


def find_production_pack_path(input_path: Path) -> Optional[Path]:
    stem = input_path.stem  # 例: 2026-09-11-a01-singularity-year-estimate-draft
    if stem.endswith("-draft"):
        candidate = input_path.parent / (stem[: -len("-draft")] + "-production-pack.md")
        if candidate.exists():
            return candidate
    return None


def parse_notes_figures(notes_text: str) -> Dict[int, dict]:
    """.notes.md の「## 挿絵」節以下から、図N ブロックをラベル付き詳細のリストとして取り出す。

    file ごとにラベル表記が揺れる（"- 位置:" / "- **位置**:" / "数値:"+"出典:" 分割 等）ため、
    厳密なキー一致ではなく「- ラベル: 内容」形式を汎用的に拾う。
    """
    lines = notes_text.splitlines()
    figures: Dict[int, dict] = {}
    current_num: Optional[int] = None
    current_title = ""
    current_fields: List[Tuple[str, str]] = []
    in_illustration_section = False

    def flush() -> None:
        nonlocal current_num, current_title, current_fields
        if current_num is not None:
            figures[current_num] = {"title": current_title, "fields": current_fields}
        current_num = None
        current_title = ""
        current_fields = []

    for line in lines:
        stripped = line.strip()
        if re.match(r"^##\s+\d*\.?\s*挿絵", stripped):
            in_illustration_section = True
            continue
        if in_illustration_section and re.match(r"^##\s+\d*\.?\s*[^挿]", stripped) and not stripped.startswith("###"):
            # 次の大見出しに入ったら挿絵節は終わり
            flush()
            in_illustration_section = False
            continue
        if not in_illustration_section:
            continue

        m = FIGURE_HEADING_RE.match(stripped)
        if m:
            flush()
            current_num = int(m.group(1))
            current_title = m.group(2).strip()
            continue

        if current_num is not None:
            bm = BULLET_FIELD_RE.match(stripped)
            if bm:
                current_fields.append((bm.group(1).strip(), bm.group(2).strip()))

    flush()
    return figures


def parse_top_image_cards(pack_text: str) -> List[dict]:
    lines = pack_text.splitlines()
    cards: List[dict] = []
    current: Optional[dict] = None
    in_section = False

    def flush() -> None:
        nonlocal current
        if current is not None:
            cards.append(current)
        current = None

    for line in lines:
        stripped = line.strip()
        if re.match(r"^##\s+\d*\.?\s*TOP\s*画像", stripped):
            in_section = True
            continue
        if in_section and stripped.startswith("## ") and "TOP" not in stripped:
            flush()
            break
        if not in_section:
            continue

        m = TOP_IMAGE_HEADING_RE.match(stripped)
        if m:
            flush()
            current = {"num": int(m.group(1)), "title": m.group(2).strip(), "concept": "", "prompt_ja": ""}
            continue

        if current is not None:
            bm = BULLET_FIELD_RE.match(stripped)
            if bm:
                label, value = bm.group(1).strip(), bm.group(2).strip()
                if label == "concept":
                    current["concept"] = value
                elif "prompt" in label and ("日本語" in label):
                    current["prompt_ja"] = value

    flush()
    return cards


def render_top_image_cards_html(cards: List[dict]) -> str:
    if not cards:
        return ""
    items = []
    for c in cards[:7]:
        title = html.escape(c.get("title", ""))
        concept = html.escape(c.get("concept", ""))
        items.append(
            '<div class="top-image-card">'
            f'<div class="top-image-card__num">案{c["num"]}</div>'
            f'<div class="top-image-card__title">{title}</div>'
            f'<div class="top-image-card__concept">{concept}</div>'
            '</div>'
        )
    return (
        '<div class="top-image-cards">'
        '<div class="top-image-cards__title">TOP 画像 7 案（production pack より、concept のみ抜粋）</div>'
        f'<div class="top-image-cards__grid">{"".join(items)}</div>'
        '</div>'
    )


# ---------------------------------------------------------------------------
# Markdown -> note風 HTML 変換
# ---------------------------------------------------------------------------

def convert_links(text: str) -> str:
    """[text](url) を note 実測どおりの属性で <a> に変換する。"""

    def _sub(m: "re.Match[str]") -> str:
        label = html.escape(m.group(1))
        url = html.escape(m.group(2), quote=True)
        return f'<a href="{url}" target="_blank" rel="noopener nofollow">{label}</a>'

    return MD_LINK_RE.sub(_sub, text)


def convert_todo_markers(text: str) -> str:
    """【…】・「本人の判定を〜」等の本人記入プレースホルダを黄色マーカーに変換する。"""

    def _sub(m: "re.Match[str]") -> str:
        inner = html.escape(m.group(1))
        return f'<span class="todo-marker" style="display:inline;">【{inner}】</span>'

    text = TODO_MARKER_RE.sub(_sub, text)

    def _sub_paren(m: "re.Match[str]") -> str:
        return f'<span class="todo-marker" style="display:inline;">{html.escape(m.group(0))}</span>'

    text = PLACEHOLDER_PAREN_RE.sub(_sub_paren, text)
    return text


def convert_inline_warnings(text: str) -> str:
    """インラインコード（`...`）を警告表示に変換する（preview-constraints.md: note に無い記法）。

    斜体（単独 *...*）は ** の太字変換より後段（bold_markdown の後）で処理するため、ここでは扱わない。
    """

    def _sub(m: "re.Match[str]") -> str:
        WARNINGS["inline_code"] += 1
        inner = html.escape(m.group(1))
        return (
            f'<code class="warn-inline-code">{inner}</code>'
            '<span class="warn-note">note では消えます</span>'
        )

    return INLINE_CODE_RE.sub(_sub, text)


def convert_italic_warnings(html_text: str) -> str:
    """** による太字変換（bold_markdown）の後に残った単独 * の斜体記法を警告表示に変換する。"""

    def _sub(m: "re.Match[str]") -> str:
        WARNINGS["italic"] += 1
        inner = m.group(1)
        return (
            f'<em class="warn-inline-italic">{inner}</em>'
            '<span class="warn-note">note では消えます</span>'
        )

    return ITALIC_RE.sub(_sub, html_text)


def render_figure_block(caption: str, detail: Optional[dict]) -> str:
    parts = ['<div class="figure-placeholder">']
    parts.append('<div class="figure-placeholder__label">🖼 図（未作成）</div>')
    parts.append(f'<div class="figure-placeholder__caption">{html.escape(caption)}</div>')
    if detail and detail.get("fields"):
        parts.append('<dl class="figure-placeholder__detail">')
        for label, value in detail["fields"]:
            parts.append(f'<dt>{html.escape(label)}</dt><dd>{convert_links(html.escape(value))}</dd>')
        parts.append('</dl>')
    else:
        parts.append(
            '<div class="figure-placeholder__missing">'
            '.notes.md の挿絵節に対応する指定が見つかりません（本文の図順と番号のずれ、'
            'または挿絵節が未整備の可能性）</div>'
        )
    parts.append('</div>')
    return "".join(parts)


def render_embed_card(url: str) -> str:
    safe_url = html.escape(url, quote=True)
    return (
        f'<a class="embed-card" href="{safe_url}" target="_blank" rel="noopener nofollow">'
        f'<div class="embed-card__label">🔗 埋め込みカード（note editor では単独行URLが自動でこの形になります）</div>'
        f'<div class="embed-card__url">{html.escape(url)}</div>'
        f'</a>'
    )


def render_table_warning(raw_lines: List[str]) -> str:
    WARNINGS["table"] += 1
    body = "\n".join(raw_lines)
    return (
        '<div class="table-warning">'
        '<div class="table-warning__label">⚠ 表（table）は note editor に規則がありません（非対応）。'
        '比較情報は箇条書きに直してください。</div>'
        f'<pre>{html.escape(body)}</pre>'
        '</div>'
    )


def md_body_to_note_html(md_text: str, figure_details: Dict[int, dict]) -> str:
    """draft本文（frontmatter除去済み）をnote風HTMLへ変換する最小実装。

    仕様上の理由でこの変換は自前実装を優先する（単独行URL・図行・【】マーカーの
    特殊変換を markdown 拡張なしで行うため）。fenced_code 等の高度な構文は扱わない。
    """
    lines = md_text.splitlines()
    out: list = []
    i = 0
    n = len(lines)
    figure_index = 0

    def inline(text: str) -> str:
        return convert_inline_warnings(convert_todo_markers(convert_links(html.escape(text))))

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # 表（markdown table）の警告
        if stripped.startswith("|") and stripped.endswith("|") and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]):
            table_lines = []
            while i < n and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            out.append(render_table_warning(table_lines))
            continue

        # 図プレースホルダ
        fig_m = FIGURE_LINE_RE.match(stripped)
        if fig_m:
            figure_index += 1
            detail = figure_details.get(figure_index)
            out.append(render_figure_block(fig_m.group(1), detail))
            i += 1
            continue

        # 単独行URL -> 埋め込みカード
        url_m = BARE_URL_LINE_RE.match(stripped)
        if url_m:
            out.append(render_embed_card(url_m.group(1)))
            i += 1
            continue

        # 見出し（H1 は H2 に丸め、丸めた旨を警告表示する。preview-constraints.md）
        if stripped.startswith("### "):
            text = inline(stripped[4:].strip())
            out.append(f"<h3>{text}</h3>")
            i += 1
            continue
        if stripped.startswith("## "):
            text = inline(stripped[3:].strip())
            out.append(f"<h2>{text}</h2>")
            i += 1
            continue
        if stripped.startswith("# "):
            WARNINGS["heading_rounded"] += 1
            text = inline(stripped[2:].strip())
            out.append(f'<h2>{text}<span class="heading-warn">（H1→H2 に丸め）</span></h2>')
            i += 1
            continue

        # 水平線（note書式では使わない方針だが、下書きに残っていれば hr として出す。
        # note実物は hr の直後に空段落が自動挿入されるため、その余白を近似する）
        if stripped in ("---", "***", "___"):
            out.append("<hr>")
            out.append('<p class="hr-gap">&nbsp;</p>')
            i += 1
            continue

        # 引用（1行 = 1 <p> で束ねる。<br> は使わない）
        if stripped.startswith(">"):
            quote_paragraphs = []
            while i < n and lines[i].strip().startswith(">"):
                quote_paragraphs.append(f"<p>{inline(lines[i].strip().lstrip('>').strip())}</p>")
                i += 1
            out.append(f"<blockquote>{''.join(quote_paragraphs)}</blockquote>")
            continue

        # 箇条書き（- / * ）
        if stripped.startswith("- ") or stripped.startswith("* "):
            items = []
            while i < n and (lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")):
                item_text = lines[i].strip()[2:].strip()
                items.append(inline(item_text))
                i += 1
            body = "".join(f"<li>{it}</li>" for it in items)
            out.append(f"<ul>{body}</ul>")
            continue

        # 番号付き箇条書き
        num_m = re.match(r"^\d+\.\s+", stripped)
        if num_m:
            items = []
            while i < n:
                s2 = lines[i].strip()
                m2 = re.match(r"^\d+\.\s+(.*)$", s2)
                if not m2:
                    break
                items.append(inline(m2.group(1)))
                i += 1
            body = "".join(f"<li>{it}</li>" for it in items)
            out.append(f"<ol>{body}</ol>")
            continue

        # 段落: note の実際の構造に合わせ、1 行 = 1 <p>（<br> でつながない）。
        # 連続する非空行は「同じ段落グループ」として連続 <p> で出す（空行が段落間の区切り）。
        while i < n and lines[i].strip() and not (
            FIGURE_LINE_RE.match(lines[i].strip())
            or BARE_URL_LINE_RE.match(lines[i].strip())
            or lines[i].strip().startswith(("#", ">", "- ", "* ", "---"))
            or re.match(r"^\d+\.\s+", lines[i].strip())
            or (lines[i].strip().startswith("|") and lines[i].strip().endswith("|"))
        ):
            out.append(f"<p>{inline(lines[i].strip())}</p>")
            i += 1

    return "\n".join(out)


def bold_markdown(html_text: str) -> str:
    """**text** を <strong> に変換する（段落生成後、htmlエスケープ済みテキストに対して行う）。"""
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html_text)


def render_toc_if_present(body_html: str) -> str:
    """本文中に H2/H3 が2つ以上あれば、note の table-of-contents に相当する枠を先頭に追加する。"""
    headings = re.findall(r"<h([23])[^>]*>(.*?)</h\1>", body_html, flags=re.S)
    if len(headings) < 2:
        return body_html
    items = []
    for level, text in headings:
        clean = re.sub(r"<span[^>]*>.*?</span>", "", text, flags=re.S).strip()
        cls = ' class="toc-h3"' if level == "3" else ""
        items.append(f"<li{cls}>{clean}</li>")
    toc = f'<div class="toc-block"><ol>{"".join(items)}</ol></div>'
    return toc + "\n" + body_html


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def extract_title(md_text: str, meta: dict) -> str:
    if meta.get("title"):
        return meta["title"]
    body = strip_frontmatter(md_text)
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# ") and not s.startswith("## "):
            return s[2:].strip()
        if s:
            return s
    return "note プレビュー"


def render(
    md_text: str,
    input_path: Path,
    template_path: Path,
    css_path: Path,
    series_registry_path: Optional[Path],
) -> Tuple[str, dict]:
    reset_warnings()
    meta = parse_frontmatter(md_text)
    title = extract_title(md_text, meta)
    body_md = strip_frontmatter(md_text)

    # 本文冒頭のタイトル単独行（frontmatterのtitleと重複する平文行）は本文から除く
    body_lines = body_md.splitlines()
    if body_lines and body_lines[0].strip() and not body_lines[0].strip().startswith("#"):
        if body_lines[0].strip() == title.strip("「」"):
            body_lines = body_lines[1:]
    body_md = "\n".join(body_lines)

    notes_path = find_notes_path(input_path, meta)
    figure_details: Dict[int, dict] = {}
    if notes_path:
        figure_details = parse_notes_figures(notes_path.read_text(encoding="utf-8"))

    pack_path = find_production_pack_path(input_path)
    top_image_cards: List[dict] = []
    if pack_path:
        top_image_cards = parse_top_image_cards(pack_path.read_text(encoding="utf-8"))

    body_html = md_body_to_note_html(body_md, figure_details)
    body_html = bold_markdown(body_html)
    body_html = convert_italic_warnings(body_html)
    body_html = render_toc_if_present(body_html)

    series_header = build_series_header(meta, series_registry_path)
    outline_html = render_outline_html(build_outline(body_md))
    top_image_html = render_top_image_cards_html(top_image_cards)

    char_count = count_body_characters(md_text)
    wordcount_line = f"字数（本文のみ／リンクURL・図を除く）: 約 {char_count:,} 字"

    warn_parts = []
    if WARNINGS["heading_rounded"]:
        warn_parts.append(f'H1→H2 丸め {WARNINGS["heading_rounded"]} 件')
    if WARNINGS["inline_code"]:
        warn_parts.append(f'インラインコード {WARNINGS["inline_code"]} 件')
    if WARNINGS["italic"]:
        warn_parts.append(f'斜体 {WARNINGS["italic"]} 件')
    if WARNINGS["table"]:
        warn_parts.append(f'表 {WARNINGS["table"]} 件')
    warning_summary = (
        f"⚠ note では再現されない記法: {'、'.join(warn_parts)}" if warn_parts else "⚠ note 非対応記法の検出: 0件"
    )

    title_html = convert_todo_markers(html.escape(title))
    title_plain = html.escape(title)

    template = template_path.read_text(encoding="utf-8")

    output_dir = input_path.parent
    css_href = os.path.relpath(css_path, output_dir)
    generated_at = datetime.datetime.now().strftime("生成: %Y-%m-%d %H:%M")

    output = (
        template
        .replace("<title>{{TITLE}}", f"<title>{title_plain}")
        .replace("{{TITLE}}", title_html)
        .replace("{{EXTRACTED_CSS_HREF}}", html.escape(css_href, quote=True))
        .replace("{{GENERATED_AT}}", html.escape(generated_at))
        .replace("{{SERIES_HEADER}}", series_header)
        .replace("{{OUTLINE}}", outline_html)
        .replace("{{TOP_IMAGE_CARDS}}", top_image_html)
        .replace("{{BODY}}", body_html)
        .replace("{{WORDCOUNT}}", html.escape(wordcount_line))
        .replace("{{WARNING_SUMMARY}}", html.escape(warning_summary))
    )
    stats = {
        "char_count": char_count,
        "warnings": dict(WARNINGS),
        "notes_path": str(notes_path) if notes_path else None,
        "production_pack_path": str(pack_path) if pack_path else None,
        "top_image_cards": len(top_image_cards),
        "figure_details_found": len(figure_details),
    }
    return output, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="draft Markdown -> 仮想note プレビュー HTML")
    parser.add_argument("input", help="入力Markdownファイル（draft）")
    parser.add_argument("-o", "--output", help="出力HTMLファイル（省略時は <入力名>.notepreview.html）")
    parser.add_argument(
        "--template",
        default=str(DEFAULT_TEMPLATE_PATH),
        help="テンプレート HTML のパス（既定: assets/note-preview/template.html）",
    )
    parser.add_argument(
        "--css",
        default=str(DEFAULT_CSS_PATH),
        help="抽出済み note CSS のパス（既定: assets/note-preview/note-textnote-body.extracted.css）",
    )
    parser.add_argument(
        "--series-registry",
        default=None,
        help="シリーズ名を引く表（Markdown table）のパス（既定: 参照しない）",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} が見つかりません", file=sys.stderr)
        sys.exit(1)

    template_path = Path(args.template)
    if not template_path.exists():
        print(f"Error: template {template_path} が見つかりません", file=sys.stderr)
        sys.exit(1)

    css_path = Path(args.css)
    if not css_path.exists():
        print(f"Error: css {css_path} が見つかりません", file=sys.stderr)
        sys.exit(1)

    series_registry_path = Path(args.series_registry) if args.series_registry else None

    md_text = input_path.read_text(encoding="utf-8")
    output_html, stats = render(md_text, input_path, template_path, css_path, series_registry_path)

    if args.output:
        output_path = Path(args.output)
    else:
        # <name>.md -> <name>.notepreview.html
        output_path = input_path.with_suffix("")
        output_path = output_path.with_suffix(".notepreview.html")

    output_path.write_text(output_html, encoding="utf-8")
    print(f"[ok] {output_path}")
    print(f"     notes: {stats['notes_path']}")
    print(f"     production_pack: {stats['production_pack_path']} (TOP画像 {stats['top_image_cards']} 案)")
    print(f"     figure_details_found: {stats['figure_details_found']}")
    print(f"     char_count: {stats['char_count']}")
    print(f"     warnings: {stats['warnings']}")


if __name__ == "__main__":
    main()
