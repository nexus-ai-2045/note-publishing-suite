#!/usr/bin/env python3
"""Fetch note official help pages into a local reference cache."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "references" / "official-note-specs" / "sources.json"
DEFAULT_OUTPUT = ROOT / "references" / "official-note-specs"


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "tr", "br"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "tr"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            text = " ".join(data.split())
            if text:
                self._chunks.append(text)

    def text(self) -> str:
        raw = html.unescape(" ".join(self._chunks))
        lines = []
        for line in raw.splitlines():
            cleaned = re.sub(r"\s+", " ", line).strip()
            if cleaned:
                lines.append(cleaned)
        return "\n".join(lines)


def fetch(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36 "
                "nexus-ai-note-official-spec-cache/1.0"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def write_markdown(
    *,
    output_dir: Path,
    key: str,
    title: str,
    category: str,
    url: str,
    html_path: Path,
    html_bytes: bytes,
    fetched_on: str,
) -> Path:
    extractor = TextExtractor()
    extractor.feed(html_bytes.decode("utf-8", errors="replace"))
    text = extractor.text()
    excerpt = "\n".join(text.splitlines()[:240])
    md_path = output_dir / "markdown" / f"{key}.md"
    md_path.write_text(
        "\n".join(
            [
                "---",
                f"title: {title}",
                f"category: {category}",
                "source_type: note_official",
                f"source_url: {url}",
                f"fetched_on: {fetched_on}",
                f"html_cache: ../html/{html_path.name}",
                "---",
                "",
                f"# {title}",
                "",
                f"- 公式URL: {url}",
                f"- 取得日: {fetched_on}",
                f"- HTMLキャッシュ: `../html/{html_path.name}`",
                "",
                "## 抽出テキスト",
                "",
                excerpt,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    output_dir = args.output_dir
    html_dir = output_dir / "html"
    markdown_dir = output_dir / "markdown"
    html_dir.mkdir(parents=True, exist_ok=True)
    markdown_dir.mkdir(parents=True, exist_ok=True)

    fetched_on = dt.date.today().isoformat()
    results = []
    for source in manifest["sources"]:
        key = source["key"]
        url = source["url"]
        html_bytes = fetch(url, args.timeout)
        html_path = html_dir / f"{key}.html"
        html_path.write_bytes(html_bytes)
        md_path = write_markdown(
            output_dir=output_dir,
            key=key,
            title=source["title"],
            category=source["category"],
            url=url,
            html_path=html_path,
            html_bytes=html_bytes,
            fetched_on=fetched_on,
        )
        results.append(
            {
                "key": key,
                "url": url,
                "html": str(html_path.relative_to(ROOT)),
                "markdown": str(md_path.relative_to(ROOT)),
                "bytes": len(html_bytes),
            }
        )

    result = {
        "manifest": str(args.manifest.relative_to(ROOT)),
        "output_dir": str(output_dir.relative_to(ROOT)),
        "fetched_on": fetched_on,
        "source_count": len(results),
        "sources": results,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"source_count={len(results)} fetched_on={fetched_on}")
        for item in results:
            print(f"{item['key']}: {item['markdown']} ({item['bytes']} bytes)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"fetch_note_official_specs: {exc}", file=sys.stderr)
        raise SystemExit(1)
