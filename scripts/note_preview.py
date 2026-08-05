#!/usr/bin/env python3
"""Create a small local HTML preview for a Note draft.

This intentionally uses only the Python standard library. It is a preview aid,
not a full Markdown renderer.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
PROVENANCE_RE = re.compile(
    r"<!--\s*(?:"
    r"provenance-label:\s*(?P<legacy_kind>[a-z-]+)"
    r"(?:\s*;\s*source:\s*(?P<legacy_source>[^;>]+?))?"
    r"|provenance\s*\n(?P<meta>.*?)\n\s*"
    r")-->\s*",
    re.S,
)
PROVENANCE_LABELS = {
    "user-said": "ユーザー発言",
    "external-fact": "確認済み外部事実",
    "assistant-organized": "AIによる整理・言い換え",
    "hold": "未確認・人間判断待ち",
}


def inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    return LINK_RE.sub(lambda m: f'<a href="{html.escape(m.group(2))}">{html.escape(m.group(1))}</a>', escaped)


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
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
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


def render_markdown(source: str, review_provenance: bool = False) -> str:
    matches = list(PROVENANCE_RE.finditer(source))
    if not matches:
        return render_plain_markdown(source)

    prefix = source[: matches[0].start()]
    rendered = [render_plain_markdown(prefix)]
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        content = source[match.end() : end]
        if not review_provenance:
            rendered.append(render_plain_markdown(content))
            continue
        metadata = parse_provenance_meta(match)
        kind = metadata["kind"]
        label = PROVENANCE_LABELS.get(kind, kind or "不明")
        rendered.append(
            f'<section class="provenance-card provenance-{html.escape(kind)}">'
            f'<div class="provenance-label">由来: {html.escape(label)}</div>'
            f'<div class="provenance-meta">source: {html.escape(metadata["source"])}'
            f' / review: {html.escape(metadata["review"] or "未指定")}</div>'
            f"{render_plain_markdown(content)}</section>"
        )
    return "\n".join(item for item in rendered if item)


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
    doc = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; line-height: 1.75; max-width: 760px; margin: 40px auto; padding: 0 20px; }}
    h1, h2, h3 {{ line-height: 1.3; }}
    a {{ color: #0969da; }}
    .provenance-card {{ border: 2px solid #8c959f; border-radius: 10px; padding: 14px 18px; margin: 20px 0; }}
    .provenance-label {{ font-weight: 700; }}
    .provenance-meta {{ color: #57606a; font-size: .9rem; }}
    .provenance-user-said {{ border-color: #1f6feb; background: #ddf4ff; }}
    .provenance-external-fact {{ border-color: #1a7f37; background: #dafbe1; }}
    .provenance-assistant-organized {{ border-color: #8250df; background: #fbefff; }}
    .provenance-hold {{ border-color: #bf8700; background: #fff8c5; }}
  </style>
</head>
<body>
{render_markdown(source, review_provenance=args.review_provenance)}
</body>
</html>
"""
    output.write_text(doc, encoding="utf-8", newline="\n")
    print(f"preview_html={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
