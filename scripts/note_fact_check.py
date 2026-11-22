#!/usr/bin/env python3
"""Find local fact-check candidates in a Note draft."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
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


X_STATUS = re.compile(r"https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/[A-Za-z0-9_]+/status(?:es)?/(\d{10,20})")
X_EPOCH_MS = 1288834974657
JST = timezone(timedelta(hours=9))


def x_post_time(post_id: int) -> str | None:
    """X投稿IDに埋め込まれた投稿時刻をJSTで返す。

    2010年11月の採番方式変更より前の連番IDは時刻を持たない。連番IDを変換すると
    エポック直後の時刻になるため、エポックから1日未満に落ちるIDは不明(None)とする。
    """
    offset_ms = post_id >> 22
    if offset_ms < 86_400_000:
        return None
    return datetime.fromtimestamp((offset_ms + X_EPOCH_MS) / 1000, JST).strftime("%Y-%m-%d %H:%M JST")


def load_terms(path: Path) -> list[dict]:
    """表記辞書JSONを読む。形式: {"terms": [{"pattern": 正規表現, "preferred": 推奨表記, "reason": 理由}]}"""
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("terms") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("表記辞書は {\"terms\": [...]} の形式で指定してください")
    terms = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get("pattern"), str) or not isinstance(item.get("preferred"), str):
            raise ValueError(f"表記辞書の{index}番目に pattern と preferred（文字列）が必要です")
        try:
            compiled = re.compile(item["pattern"])
        except re.error as exc:
            raise ValueError(f"表記辞書の{index}番目の pattern が不正です: {exc}") from exc
        terms.append({"regex": compiled, "preferred": item["preferred"], "reason": str(item.get("reason", ""))})
    return terms


def scan(text: str, terms: list[dict] | None = None) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for code, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append({"line": line_no, "code": code, "text": line.strip()[:180]})
        for match in X_STATUS.finditer(line):
            posted = x_post_time(int(match.group(1)))
            findings.append({
                "line": line_no,
                "code": "x_post_time",
                "text": line.strip()[:180],
                "post_id": match.group(1),
                "posted_at_jst": posted or "unknown",
            })
        for term in terms or []:
            for match in term["regex"].finditer(line):
                findings.append({
                    "line": line_no,
                    "code": "term_mismatch",
                    "text": line.strip()[:180],
                    "found": match.group(0),
                    "preferred": term["preferred"],
                    "reason": term["reason"],
                })
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
    parser.add_argument("--terms", type=Path, help="利用者が採用した表記辞書JSON。一致箇所を term_mismatch として出す（自動修正しない）")
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
    terms = None
    if args.terms:
        try:
            terms = load_terms(args.terms)
        except (OSError, ValueError) as exc:
            parser.error(f"表記辞書を読めません: {exc}")
    draft_bytes = args.draft.read_bytes()
    findings = scan(draft_bytes.decode("utf-8"), terms)
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
            extra = ""
            if item["code"] == "x_post_time":
                extra = f" posted_at={item['posted_at_jst']}"
            elif item["code"] == "term_mismatch":
                extra = f" found={item['found']} preferred={item['preferred']}"
            print(f"line={item['line']} code={item['code']}{extra} text={item['text']}")
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
