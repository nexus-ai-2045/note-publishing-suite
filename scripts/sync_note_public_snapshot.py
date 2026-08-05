#!/usr/bin/env python3
"""公開済みNote本文を来歴付きMarkdownとしてローカル保存する。"""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def fetch_published_text(url: str) -> str:
    match = re.search(r"note\.com/[^/]+/n/([A-Za-z0-9_-]+)", url)
    if match is None:
        raise ValueError("note URL から note_id を抽出できません")
    request = urllib.request.Request(
        f"https://note.com/api/v3/notes/{match.group(1)}",
        headers={"Accept": "application/json", "User-Agent": "note-public-snapshot/1"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    data = payload["data"]
    if data.get("status") != "published":
        raise ValueError("note記事がpublishedではありません")
    body = str(data.get("body") or "")
    text = re.sub(r"<br\s*/?>", "\n", body, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|h[1-6]|li|blockquote)>", "\n", text, flags=re.IGNORECASE)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="公開済みNote本文のローカルsnapshotを作る")
    parser.add_argument("--url", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-draft", required=True)
    args = parser.parse_args(argv)

    body = fetch_published_text(args.url)
    captured_at = datetime.now(timezone.utc).isoformat()
    text = "\n".join(
        [
            "---",
            "schema_version: note-public-snapshot/v1",
            f"title: {quote(args.title)}",
            f"source_url: {quote(args.url)}",
            f"source_draft: {quote(args.source_draft)}",
            f"captured_at: {quote(captured_at)}",
            "captured_by: codex",
            "source_kind: public_note",
            "external_action: none",
            "---",
            "",
            f"# {args.title}",
            "",
            body.strip(),
            "",
        ]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(args.output), "body_char_count": len(body), "captured_at": captured_at, "external_actions": []}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
