#!/usr/bin/env python3
"""Find local fact-check candidates in a Note draft."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


PATTERNS = {
    "uncertain_claim": re.compile(r"(未確認|要確認|推測|多分|おそらく|らしい|かもしれない)"),
    "number_or_percent": re.compile(r"(\d[\d,]*(?:\.\d+)?\s*(?:%|円|人|件|年|月|日)?)"),
    "url": re.compile(r"https?://[^\s)]+"),
    "internal_note": re.compile(r"(内部メモ|下書きメモ|TODO|FIXME)", re.I),
    "personal_experience_claim": re.compile(
        r"(私|僕|俺|自分|わたし|ぼく).{0,24}(感じた|思った|考えた|体験|経験|見た|聞いた|試した|やってみた|気づいた)"
        r"|(?:体験|経験|実感|自分の発言|自分の言葉|本人の言葉|発言ベース|体験ベース)"
    ),
    "source_provenance_marker": re.compile(
        r"(source|出典|出典ノート|根拠|引用元|発言ログ|会話ログ|素材|体験メモ|原文)"
    ),
}


def scan(text: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for code, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append({"line": line_no, "code": code, "text": line.strip()[:180]})
    return findings


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_endpoint(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme != "http"
        or parts.hostname not in {"127.0.0.1", "[::1]", "::1"}
        or parts.username is not None
        or parts.password is not None
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        raise ValueError("検索APIはローカルの http://127.0.0.1:port または http://[::1]:port を指定してください")
    _ = parts.port
    return value.rstrip("/")


def search_sources(query: str, endpoint: str, limit: int) -> dict:
    result = {
        "query": query,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "status": "error",
        "verification": "unverified",
        "candidates": [],
        "unresponsive_engines": [],
    }
    try:
        url = endpoint + "/search?" + urlencode({"q": query, "format": "json", "language": "ja-JP"})
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(Request(url, headers={"Accept": "application/json"}), timeout=20) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("検索応答が上限を超えました")
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ValueError("検索応答の形式が不正です")
        failures = data.get("unresponsive_engines", [])
        if not isinstance(failures, list):
            raise ValueError("検索先の失敗情報の形式が不正です")
        result["unresponsive_engines"] = failures
        seen = set()
        for item in data["results"]:
            if not isinstance(item, dict):
                raise ValueError("検索候補の形式が不正です")
            link = item.get("url")
            if not isinstance(link, str) or urlsplit(link).scheme not in {"http", "https"} or link in seen:
                continue
            seen.add(link)
            result["candidates"].append({
                "url": link,
                "title": str(item.get("title", ""))[:500],
                "snippet": str(item.get("content", ""))[:1500],
                "engines": item.get("engines", []),
                "body_status": "not_fetched",
                "verification": "unverified",
            })
            if len(result["candidates"]) >= limit:
                break
        result["status"] = "partial" if failures else "ok"
        if not result["candidates"]:
            result["status"] = "unavailable" if failures else "no_results"
    except (URLError, OSError, ValueError) as exc:
        result["error"] = str(exc)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["local"])
    parser.add_argument("draft", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--search-query", action="append", default=[], help="出典候補を探す検索語。指定した語だけを外部検索先へ送信")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8888", help="ローカルSearXNGのURL")
    parser.add_argument("--limit", type=int, default=5, help="検索語ごとの候補数（1〜20）")
    parser.add_argument("--dry-run", action="store_true", help="検索語と送信先の確認のみ。通信・保存しない")
    parser.add_argument("--report-path", type=Path, help="候補と未確認状態をJSON保存（既存ファイルは上書きしない）")
    args = parser.parse_args()

    if not 1 <= args.limit <= 20 or len(args.search_query) > 10:
        parser.error("候補数は1〜20、検索語は最大10件です")
    if any(not q.strip() or len(q) > 500 for q in args.search_query):
        parser.error("検索語は空欄不可、最大500文字です")
    try:
        endpoint = local_endpoint(args.endpoint)
    except ValueError as exc:
        parser.error(str(exc))
    if args.report_path and args.report_path.exists() and not args.dry_run:
        parser.error("既存のレポートは上書きしません。別の保存先を指定してください")
    draft_bytes = args.draft.read_bytes()
    findings = scan(draft_bytes.decode("utf-8"))
    result = {"draft": str(args.draft), "mode": args.mode, "finding_count": len(findings), "findings": findings}
    exit_code = 0
    if args.search_query or args.report_path or args.dry_run:
        result.update(
            draft_sha256=hashlib.sha256(draft_bytes).hexdigest(),
            observed_at=datetime.now(timezone.utc).isoformat(),
            verification="unverified",
            publication="disabled",
            dry_run=args.dry_run,
            search_endpoint=endpoint,
            search_queries=args.search_query,
            search_results=[],
        )
        if not args.dry_run:
            result["search_results"] = [search_sources(q, endpoint, args.limit) for q in args.search_query]
            if any(s["status"] in {"error", "unavailable"} for s in result["search_results"]):
                exit_code = 2
            if args.report_path:
                args.report_path.parent.mkdir(parents=True, exist_ok=True)
                with args.report_path.open("x", encoding="utf-8") as report:
                    json.dump(result, report, ensure_ascii=False, indent=2)
                    report.write("\n")
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(f"finding_count={len(findings)}")
        for item in findings:
            print(f"line={item['line']} code={item['code']} text={item['text']}")
        if args.dry_run:
            print(f"通信なし: endpoint={endpoint} queries={args.search_query}")
        for search in result.get("search_results", []):
            print(f"検索={search['query']} 状態={search['status']} 本文未確認・真偽未検証")
            for item in search["candidates"]:
                print(f"  {item['title']} {item['url']}")
            if search.get("error"):
                print(f"  エラー: {search['error']}")
            if search["unresponsive_engines"]:
                print(f"  応答しなかった検索先: {search['unresponsive_engines']}")
        if args.report_path and not args.dry_run:
            print(f"保存先: {args.report_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
