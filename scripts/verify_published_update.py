#!/usr/bin/env python3
"""公開済みNote記事の更新結果を、公開APIの現在値で読み取り照合する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sync_note_public_snapshot import extract_published_text, fetch_published_data


def parse_note_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    match = re.fullmatch(r"/([^/]+)/n/(n[0-9a-fA-F]+?)/?", parsed.path)
    if parsed.scheme != "https" or parsed.netloc != "note.com" or not match or parsed.query or parsed.fragment:
        raise ValueError("https://note.com/<user>/n/<note-id> の公開URLが必要です")
    return match.group(1), match.group(2)


def image_asset_identity(url: object) -> tuple[str, str] | None:
    if not isinstance(url, str):
        return None
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError:
        return None
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or port is not None
            or not parsed.path or parsed.path == "/" or parsed.fragment):
        return None
    return parsed.hostname.lower(), parsed.path


def verify_ledger(rows: object, *, live: dict) -> dict:
    if not isinstance(rows, list):
        return {"overall": "blocked", "reason": "ledger_must_be_list"}

    def same_note(row: object) -> bool:
        if not isinstance(row, dict):
            return False
        if row.get("note_id") == live["note_id"]:
            return True
        try:
            return parse_note_url(row.get("url", ""))[1] == live["note_id"]
        except (ValueError, TypeError):
            return False

    matches = [row for row in rows if same_note(row)]
    if len(matches) != 1:
        return {"overall": "blocked", "reason": "note_id_row_count", "matching_rows": len(matches)}
    row = matches[0]
    hashes = [row[key] for key in ("published_body_sha256", "public_body_sha256") if key in row]
    checks = {
        "url_matches": row.get("url") == live["url"],
        "note_id_matches": row.get("note_id", live["note_id"]) == live["note_id"],
        "title_matches": row.get("title") == live["title"],
        "eyecatch_matches": image_asset_identity(row.get("image_url")) == image_asset_identity(live["eyecatch_url"])
        and image_asset_identity(row.get("image_url")) is not None,
        "status_verified": (
            row.get("verification_status") == "published_verified"
            if "verification_status" in row
            else row.get("plain_status") == "published_verified"
        ),
        "status_published": "status" not in row or row.get("status") == "published",
        "body_sha256_matches": bool(hashes) and all(value == live["body_sha256"] for value in hashes),
    }
    return {"overall": "ok" if all(checks.values()) else "blocked", "checks": checks}


def verify(data: dict, *, url: str, expected_title: str, expected_eyecatch_url: str,
           contains: list[str], absent: list[str]) -> dict:
    owner, note_id = parse_note_url(url)
    body = extract_published_text(data) if data.get("status") == "published" else ""
    user = data.get("user")
    expected_asset = image_asset_identity(expected_eyecatch_url)
    observed_asset = image_asset_identity(data.get("eyecatch"))
    checks = {
        "status_published": data.get("status") == "published",
        "body_present": bool(body),
        "note_id_matches": data.get("key") == note_id,
        "owner_matches": isinstance(user, dict) and user.get("urlname") == owner,
        "title_matches": data.get("name") == expected_title,
        "eyecatch_matches": expected_asset is not None and observed_asset == expected_asset,
        "contains_phrases": {phrase: phrase in body for phrase in contains},
        "absent_phrases": {phrase: phrase not in body for phrase in absent},
    }
    passed = all(value for key, value in checks.items() if key not in ("contains_phrases", "absent_phrases"))
    passed = passed and all(checks["contains_phrases"].values()) and all(checks["absent_phrases"].values())
    return {
        "overall": "ok" if passed else "blocked",
        "source": "live_public_note_api",
        "url": url,
        "note_id": note_id,
        "title": data.get("name"),
        "eyecatch_url": data.get("eyecatch"),
        "eyecatch_asset_identity": observed_asset,
        "published_at": data.get("publish_at"),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest() if body else None,
        "checks": checks,
        "body": body,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--expected-title", required=True)
    parser.add_argument("--expected-eyecatch-url", required=True)
    parser.add_argument("--contains", action="append", default=[])
    parser.add_argument("--absent", action="append", default=[])
    parser.add_argument("--ledger", type=Path, help="既存のpublished_notes.jsonを読み取り照合する")
    args = parser.parse_args(argv)
    if not args.expected_title.strip() or image_asset_identity(args.expected_eyecatch_url) is None:
        parser.error("空でない題名と正しい https のアイキャッチURLが必要です")
    if any(not phrase for phrase in (*args.contains, *args.absent)):
        parser.error("本文句に空文字列は使えません")
    try:
        parse_note_url(args.url)
        result = verify(
            fetch_published_data(args.url), url=args.url,
            expected_title=args.expected_title,
            expected_eyecatch_url=args.expected_eyecatch_url,
            contains=args.contains, absent=args.absent,
        )
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"overall": "blocked", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    result.pop("body")
    if args.ledger:
        try:
            rows = json.loads(args.ledger.read_text(encoding="utf-8"))
            result["ledger"] = verify_ledger(rows, live=result)
        except (OSError, ValueError, TypeError) as exc:
            result["ledger"] = {"overall": "blocked", "reason": str(exc)}
        if result["ledger"]["overall"] != "ok":
            result["overall"] = "blocked"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["overall"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
