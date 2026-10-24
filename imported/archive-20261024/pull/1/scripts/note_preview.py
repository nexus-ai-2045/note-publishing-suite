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


def inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    return LINK_RE.sub(lambda m: f'<a href="{html.escape(m.group(2))}">{html.escape(m.group(1))}</a>', escaped)


def render_markdown(source: str) -> str:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("-o", "--output", type=Path)
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
  </style>
</head>
<body>
{render_markdown(source)}
</body>
</html>
"""
    output.write_text(doc, encoding="utf-8", newline="\n")
    print(f"preview_html={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
