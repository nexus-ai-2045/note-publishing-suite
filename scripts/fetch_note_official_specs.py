#!/usr/bin/env python3
"""Fetch note official help pages into a local reference cache."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import hashlib
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from sync_note_public_snapshot import atomic_write_bytes, reject_file_aliases


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "references" / "official-note-specs" / "sources.json"

def validate_url(url: object) -> str:
    if not isinstance(url, str):
        raise ValueError("公式URLが文字列ではありません")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc not in {"www.help-note.com", "help-note.com"}
            or not re.fullmatch(r"/hc/ja/articles/[0-9]+(?:-[^/?#]+)?", parsed.path)
            or parsed.query or parsed.fragment):
        raise ValueError("対象は認証情報を含まないnote公式ヘルプ記事のHTTPS URLに限定します")
    return url


class OfficialRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_manifest(manifest: object) -> list[dict]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("sources"), list) or not manifest["sources"]:
        raise ValueError("sourcesには空でない配列が必要です")
    keys = set()
    for source in manifest["sources"]:
        if not isinstance(source, dict):
            raise ValueError("sourceはobjectである必要があります")
        key = source.get("key")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", key) or key in keys:
            raise ValueError("source keyが不正または重複しています")
        keys.add(key)
        for name in ("title", "category"):
            if not isinstance(source.get(name), str) or not source[name].strip() or "\n" in source[name] or "\r" in source[name]:
                raise ValueError(f"source {name}が不正です")
        validate_url(source.get("url"))
    return manifest["sources"]



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
        validate_url(url),
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
    with urllib.request.build_opener(OfficialRedirectHandler()).open(request, timeout=timeout) as response:
        validate_url(response.geturl())
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
    markdown = "\n".join(
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
    ).encode("utf-8")
    atomic_write_bytes(md_path, markdown)
    if md_path.read_bytes() != markdown:
        raise ValueError("Markdown保存後の読戻しが一致しません")
    return md_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, required=True, help="workspaceが選択したpackage外のprivate参照保存先")
    parser.add_argument("--allow-public-http", action="store_true", help="公式公開HTTPSの取得とcache保存を明示許可。既定は計画表示のみ")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    sources = validate_manifest(manifest)
    output_dir = args.output_dir.expanduser().resolve()
    if output_dir.is_relative_to(ROOT):
        raise ValueError("cache保存先はNPS package外を指定してください")
    outputs = [output_dir / kind / f"{source['key']}.{suffix}"
               for source in sources for kind, suffix in (("html", "html"), ("markdown", "md"))]
    if any(not path.resolve().is_relative_to(output_dir) for path in outputs):
        raise ValueError("cache保存先から外へ出るsymlinkは使用できません")
    reject_file_aliases([args.manifest], outputs)
    if not args.allow_public_http:
        print(json.dumps({"mode": "dry-run", "output_dir": str(output_dir), "source_count": len(sources), "sources": sources}, ensure_ascii=False, indent=2))
        return 0
    html_dir = output_dir / "html"
    markdown_dir = output_dir / "markdown"
    html_dir.mkdir(parents=True, exist_ok=True)
    markdown_dir.mkdir(parents=True, exist_ok=True)

    fetched_on = dt.date.today().isoformat()
    results = []
    for source in sources:
        key = source["key"]
        url = source["url"]
        html_bytes = fetch(url, args.timeout)
        html_path = html_dir / f"{key}.html"
        atomic_write_bytes(html_path, html_bytes)
        if html_path.read_bytes() != html_bytes:
            raise ValueError("HTML保存後の読戻しが一致しません")
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
                "html": str(html_path),
                "markdown": str(md_path),
                "html_sha256": hashlib.sha256(html_bytes).hexdigest(),
                "markdown_sha256": hashlib.sha256(md_path.read_bytes()).hexdigest(),
                "bytes": len(html_bytes),
            }
        )

    result = {
        "mode": "fetched",
        "manifest": str(args.manifest.resolve()),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "output_dir": str(output_dir),
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
