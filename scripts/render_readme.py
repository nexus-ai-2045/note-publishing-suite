#!/usr/bin/env python3
"""Render README.md to README.rendered.html with a conservative Markdown subset."""

from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
OUTPUT = ROOT / "README.rendered.html"


def inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)

    def render_link(match: re.Match[str]) -> str:
        label, escaped_target = match.groups()
        target = html.unescape(escaped_target)
        parsed = urlsplit(target)
        is_safe = parsed.scheme in {"", "http", "https"} and not target.startswith("//")
        if not is_safe:
            return match.group(0)
        safe_target = html.escape(target, quote=True)
        return f'<a href="{safe_target}">{label}</a>'

    escaped = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", render_link, escaped)
    return escaped


def strip_frontmatter(lines: list[str]) -> list[str]:
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return lines[index + 1 :]
    return lines


def render(markdown: str) -> str:
    lines = strip_frontmatter(markdown.splitlines())
    out: list[str] = []
    in_ul = False
    in_pre = False
    pre_lines: list[str] = []
    para: list[str] = []
    table_lines: list[str] = []

    def is_table_separator(line: str) -> bool:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells:
            return False
        return all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)

    def split_table_row(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    def close_para() -> None:
        nonlocal para
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para = []

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    def close_pre() -> None:
        nonlocal in_pre, pre_lines
        if in_pre:
            out.append("<pre><code>" + html.escape("\n".join(pre_lines)) + "</code></pre>")
            pre_lines = []
            in_pre = False

    def close_table() -> None:
        nonlocal table_lines
        if not table_lines:
            return
        if len(table_lines) >= 2 and is_table_separator(table_lines[1]):
            headers = split_table_row(table_lines[0])
            rows = [split_table_row(row) for row in table_lines[2:]]
            out.append("<div class=\"table-wrap\"><table>")
            out.append(
                "<thead><tr>"
                + "".join(f"<th>{inline(header)}</th>" for header in headers)
                + "</tr></thead>"
            )
            out.append("<tbody>")
            for row in rows:
                cells = row + [""] * max(0, len(headers) - len(row))
                out.append(
                    "<tr>"
                    + "".join(f"<td>{inline(cell)}</td>" for cell in cells[: len(headers)])
                    + "</tr>"
                )
            out.append("</tbody></table></div>")
        else:
            for table_line in table_lines:
                out.append(f"<p>{inline(table_line.strip())}</p>")
        table_lines = []

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("```"):
            if in_pre:
                close_pre()
            else:
                close_para()
                close_ul()
                in_pre = True
                pre_lines = []
            continue
        if in_pre:
            pre_lines.append(line)
            continue
        if line.strip().startswith("|") and line.strip().endswith("|"):
            close_para()
            close_ul()
            table_lines.append(line)
            continue
        close_table()
        if not line.strip():
            close_para()
            close_ul()
            continue
        stripped = line.strip()
        if stripped in {"<details>", "</details>"}:
            close_para()
            close_ul()
            out.append(stripped)
            continue
        summary = re.fullmatch(r"<summary>(.+)</summary>", stripped)
        if summary:
            close_para()
            close_ul()
            out.append(f"<summary>{inline(summary.group(1))}</summary>")
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            close_para()
            close_ul()
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            continue
        if line.startswith("- "):
            close_para()
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline(line[2:].strip())}</li>")
            continue
        para.append(line.strip())
    close_pre()
    close_table()
    close_para()
    close_ul()
    return "\n".join(out)


def main() -> int:
    body = render(README.read_text(encoding="utf-8"))
    doc = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Note Publishing Suite README</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f8fb;
      --paper: #ffffff;
      --text: #172033;
      --muted: #5b667a;
      --line: #dfe5ee;
      --accent: #23845f;
      --code: #eef4f1;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #101418;
        --paper: #171c22;
        --text: #eef3f7;
        --muted: #a6b0bd;
        --line: #2b333d;
        --accent: #59d49f;
        --code: #1f2a26;
      }}
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.75;
    }}
    main {{
      max-width: 920px;
      margin: 0 auto;
      padding: 48px 20px 72px;
    }}
    article {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 36px;
    }}
    h1 {{ margin: 0 0 12px; font-size: 2rem; line-height: 1.25; }}
    h2 {{ margin-top: 34px; padding-top: 20px; border-top: 1px solid var(--line); font-size: 1.35rem; }}
    h3 {{ margin-top: 24px; font-size: 1.05rem; }}
    p {{ margin: 12px 0; }}
    ul {{ padding-left: 1.3rem; }}
    li {{ margin: 8px 0; }}
    details {{
      margin: 24px 0;
      padding-top: 16px;
      border-top: 1px solid var(--line);
    }}
    summary {{
      cursor: pointer;
      color: var(--accent);
      font-weight: 650;
    }}
    details[open] summary {{ margin-bottom: 16px; }}
    details h2:first-of-type {{ margin-top: 0; }}
    .table-wrap {{
      margin: 18px 0;
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 720px;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: 0.9rem;
      font-weight: 650;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    code {{
      border-radius: 5px;
      padding: 0.12rem 0.35rem;
      background: var(--code);
      color: var(--accent);
      font-family: "Cascadia Mono", Consolas, monospace;
      overflow-wrap: anywhere;
    }}
    pre {{
      overflow-x: auto;
      border-radius: 8px;
      padding: 14px 16px;
      background: var(--code);
      border: 1px solid var(--line);
    }}
    pre code {{ padding: 0; background: transparent; color: var(--text); }}
  </style>
</head>
<body>
  <main>
    <article>
{body}
    </article>
  </main>
</body>
</html>
"""
    OUTPUT.write_text(doc, encoding="utf-8", newline="\n")
    print(f"rendered_html={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
