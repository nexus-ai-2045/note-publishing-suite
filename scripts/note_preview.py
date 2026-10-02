#!/usr/bin/env python3
"""Create a small local HTML preview for a Note draft.

This intentionally uses only the Python standard library. It is a preview aid,
not a full Markdown renderer.
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import re
import sys
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVENANCE_LABEL_CHECK = ROOT / "scripts" / "provenance_label_check.py"

LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
LINK_TARGET_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
PROVENANCE_RE = re.compile(
    r"<!--\s*(?:"
    r"provenance-label:\s*(?P<legacy_kind>[a-z-]+)"
    r"(?:\s*;\s*source:\s*(?P<legacy_source>[^;>]+?))?"
    r"|provenance\s*\n(?P<meta>.*?)\n\s*"
    r")--!?>\s*",
    re.S,
)
# 種類ごとの短い名前。並び順がレビュー画面の件数表示の順になる。
# 色は CSS の .prov-<kind> が持つ（本人=緑、AIのつなぎ=黄、資料の事実=青、保留=赤）。
PROVENANCE_LABELS = {
    "user-said": "本人",
    "assistant-organized": "AIのつなぎ",
    "external-fact": "資料の事実",
    "hold": "保留",
}


@lru_cache(maxsize=1)
def load_provenance_label_check():
    name = "provenance_label_check"
    spec = importlib.util.spec_from_file_location(name, PROVENANCE_LABEL_CHECK)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load provenance_label_check.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def split_frontmatter(source: str) -> tuple[dict[str, object], str]:
    """先頭の `---` 行から次の `---` 行までを設定部分として本文から外す。

    判定は由来ラベル検査と同じ関数を使う。閉じる `---` がなければ本文として扱う。
    """
    frontmatter, body, _ = load_provenance_label_check().split_frontmatter(source)
    return frontmatter, body


def inline_markdown(text: str) -> str:
    # escape 済みの文字列に当てるので、取り出した部分は再 escape しない。
    escaped = html.escape(text)
    return LINK_RE.sub(
        lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener">{m.group(1)}</a>',
        escaped,
    )


def render_plain_markdown(source: str) -> str:
    lines = source.splitlines()
    body: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            body.append("</ul>")
            in_list = False

    for raw in lines:
        line = raw.rstrip()
        if not line:
            close_list()
            continue
        if line.startswith("---"):
            close_list()
            body.append("<hr>")
            continue
        match = HEADING_RE.match(line)
        if match:
            close_list()
            level = len(match.group(1))
            body.append(f"<h{level}>{inline_markdown(match.group(2))}</h{level}>")
            continue
        if line.startswith(("- ", "* ")):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{inline_markdown(line[2:].strip())}</li>")
            continue
        close_list()
        body.append(f"<p>{inline_markdown(line)}</p>")
    close_list()
    return "\n".join(body)


def parse_provenance_meta(match: re.Match[str]) -> dict[str, str]:
    metadata = {
        "kind": (match.group("legacy_kind") or "").strip(),
        "source": (match.group("legacy_source") or "").strip(),
        "review": "",
    }
    for raw in (match.group("meta") or "").splitlines():
        if ":" in raw:
            key, value = raw.split(":", 1)
            metadata[key.strip()] = value.strip()
    return metadata


def split_provenance_blocks(body: str) -> tuple[str, list[tuple[dict[str, str], str]]]:
    matches = list(PROVENANCE_RE.finditer(body))
    if not matches:
        return body, []
    blocks = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        blocks.append((parse_provenance_meta(match), body[match.end() : end]))
    return body[: matches[0].start()], blocks


def review_items(content: str) -> list[tuple[bool, str]]:
    """本文を (色の塊の中に置くか, html) の並びにする。

    見出しと区切り線は塊の外に出す。続けて書いた行は 1 段落にまとめ、改行は <br> で残す。
    """
    items: list[tuple[bool, str]] = []
    paragraph: list[str] = []
    bullets: list[str] = []

    def flush() -> None:
        if paragraph:
            items.append((True, "<p>" + "<br>".join(paragraph) + "</p>"))
            paragraph.clear()
        if bullets:
            items.append((True, "<ul>" + "".join(f"<li>{item}</li>" for item in bullets) + "</ul>"))
            bullets.clear()

    for raw in content.splitlines():
        line = raw.strip()
        heading = HEADING_RE.match(line)
        if not line:
            flush()
        elif line.startswith("---"):
            flush()
            items.append((False, "<hr>"))
        elif heading:
            flush()
            level = len(heading.group(1))
            items.append((False, f"<h{level}>{inline_markdown(heading.group(2))}</h{level}>"))
        elif line.startswith(("- ", "* ")):
            if paragraph:
                flush()
            bullets.append(inline_markdown(line[2:].strip()))
        else:
            if bullets:
                flush()
            paragraph.append(inline_markdown(line))
    flush()
    return items


def body_chars(content: str) -> int:
    """見出し・区切り線・空白・リンク先を除いた字数。"""
    total = 0
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("---") or HEADING_RE.match(line):
            continue
        if line.startswith(("- ", "* ")):
            line = line[2:]
        total += len(re.sub(r"\s", "", LINK_TARGET_RE.sub(r"\1", line)))
    return total


def kind_class(kind: str) -> str:
    return kind if kind in PROVENANCE_LABELS else "unknown"


def render_review_block(metadata: dict[str, str], content: str) -> str:
    kind = metadata["kind"]
    name = PROVENANCE_LABELS.get(kind, kind or "不明")
    source = metadata["source"] or "source 未記入"
    if metadata["review"]:
        source += f" / review: {metadata['review']}"

    def card(inner: str) -> str:
        return (
            f'<section class="prov-block prov-{kind_class(kind)}">'
            f'<span class="prov-tag">{html.escape(name)}</span>{inner}'
            f'<div class="prov-src">{html.escape(source)}</div></section>'
        )

    parts: list[str] = []
    inside: list[str] = []
    carded = False
    for in_card, piece in review_items(content):
        if in_card:
            inside.append(piece)
            continue
        if inside:
            parts.append(card("".join(inside)))
            inside, carded = [], True
        parts.append(piece)
    if inside or not carded:
        # 見出しだけの塊でも、由来が見えなくならないよう空の塊を残す。
        parts.append(card("".join(inside)))
    return "".join(parts)


def render_review(
    frontmatter: dict[str, object],
    prefix: str,
    blocks: list[tuple[dict[str, str], str]],
) -> str:
    counts: dict[str, int] = {}
    chars = body_chars(prefix)
    rendered = ["".join(piece for _, piece in review_items(prefix))]
    for metadata, content in blocks:
        kind = metadata["kind"]
        counts[kind] = counts.get(kind, 0) + 1
        if kind != "hold":
            chars += body_chars(content)
        rendered.append(render_review_block(metadata, content))

    names = dict(PROVENANCE_LABELS)
    names.update({kind: kind or "不明" for kind in counts if kind not in PROVENANCE_LABELS})
    chips = "".join(
        f'<span class="prov-chip prov-{kind_class(kind)}">{html.escape(name)} {counts.get(kind, 0)}</span>'
        for kind, name in names.items()
    )
    header = ['<header class="prov-summary">']
    title = str(frontmatter.get("title") or "").strip()
    body_text = prefix + "".join(content for _, content in blocks)
    if title and not re.search(r"(?m)^#\s", body_text):
        header.append(f"<h1>{html.escape(title)}</h1>")
    header.append(f'<p class="prov-chips">{chips}</p>')
    header.append(
        f'<p class="prov-note">本文 約{chars:,}字（空白・リンク先・見出し・保留を除く）。'
        "色は由来、右上の小さい字が種類、下の灰色の字が source。</p>"
    )
    header.append("</header>")
    return "\n".join(["".join(header), *(item for item in rendered if item)])


def render_markdown(source: str, review_provenance: bool = False) -> str:
    # Windows で保存した下書きの先頭 BOM があると frontmatter と判定できない。
    frontmatter, body = split_frontmatter(source.lstrip("﻿"))
    prefix, blocks = split_provenance_blocks(body)
    if review_provenance:
        return render_review(frontmatter, prefix, blocks)
    rendered = [render_plain_markdown(prefix), *(render_plain_markdown(content) for _, content in blocks)]
    return "\n".join(item for item in rendered if item)


STYLE = """
    :root { --bg: #f6f5f1; --panel: #fff; --ink: #1f2328; --muted: #646c77; --line: #e2dfd8; --accent: #2f3a8f;
      --self: #1a7a4b; --self-bg: #eef8f2; --ai: #9a5a00; --ai-bg: #fdf6e8;
      --fact: #2b5fb4; --fact-bg: #eef3fc; --hold: #c0262f; --hold-bg: #fde8ea; }
    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) { --bg: #15171b; --panel: #1e2127; --ink: #e7e7e4; --muted: #a2a8b2;
        --line: #30343b; --accent: #aab1ff; --self: #6fd3a0; --self-bg: #16261f; --ai: #f2bb63; --ai-bg: #2a2216;
        --fact: #8fb6ff; --fact-bg: #18202e; --hold: #ff8f99; --hold-bg: #3a1d21; }
    }
    :root[data-theme="dark"] { --bg: #15171b; --panel: #1e2127; --ink: #e7e7e4; --muted: #a2a8b2;
      --line: #30343b; --accent: #aab1ff; --self: #6fd3a0; --self-bg: #16261f; --ai: #f2bb63; --ai-bg: #2a2216;
      --fact: #8fb6ff; --fact-bg: #18202e; --hold: #ff8f99; --hold-bg: #3a1d21; }
    body { font-family: "Hiragino Sans", "Noto Sans JP", system-ui, sans-serif; line-height: 1.85; max-width: 760px;
      margin: 40px auto; padding: 0 16px; background: var(--bg); color: var(--ink); }
    h1, h2, h3 { line-height: 1.3; }
    a { color: var(--accent); }
    .review h1 { font-size: 1.25rem; margin: 4px 0; }
    .review h2 { font-size: 1.3rem; margin: 30px 0 8px; padding: 4px 10px; border-left: 6px solid var(--accent);
      background: var(--panel); border-radius: 6px; }
    .review h3 { font-size: 1.1rem; margin: 18px 0 6px; padding-left: 8px; border-left: 3px solid var(--line); }
    .prov-user-said { --kind: var(--self); --kind-bg: var(--self-bg); }
    .prov-assistant-organized { --kind: var(--ai); --kind-bg: var(--ai-bg); }
    .prov-external-fact { --kind: var(--fact); --kind-bg: var(--fact-bg); }
    .prov-hold { --kind: var(--hold); --kind-bg: var(--hold-bg); }
    .prov-summary { margin-bottom: 12px; }
    .prov-note { font-size: .8rem; color: var(--muted); margin: 0 0 6px; }
    .prov-chip { display: inline-block; font-size: .78rem; font-weight: 700; border-radius: 999px; padding: 0 9px;
      margin: 0 4px 4px 0; color: var(--kind, var(--muted)); background: var(--kind-bg, var(--panel)); }
    .prov-block { margin: 8px 0; padding: 6px 12px 4px; border-left: 4px solid var(--kind, var(--muted));
      border-radius: 4px; background: var(--kind-bg, var(--panel)); }
    .prov-block.prov-hold { font-weight: 600; }
    .prov-block p, .prov-block ul { margin: 0 0 6px; }
    .prov-tag { float: right; margin-left: 8px; font-size: .7rem; font-weight: 700; opacity: .8;
      color: var(--kind, var(--muted)); }
    .prov-src { font-size: .72rem; line-height: 1.5; color: var(--muted); margin-bottom: 2px; overflow-wrap: anywhere; }
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument(
        "--review-provenance",
        action="store_true",
        help="由来ラベルを色分けした人間レビュー用 HTML を生成する。",
    )
    args = parser.parse_args()

    source = args.draft.read_text(encoding="utf-8")
    output = args.output or args.draft.with_suffix(".html")
    title = args.draft.stem
    body_class = ' class="review"' if args.review_provenance else ""
    doc = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{STYLE}  </style>
</head>
<body{body_class}>
{render_markdown(source, review_provenance=args.review_provenance)}
</body>
</html>
"""
    output.write_text(doc, encoding="utf-8", newline="\n")
    print(f"preview_html={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
