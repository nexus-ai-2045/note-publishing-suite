#!/usr/bin/env python3
"""Compare a local draft with a fetched Note/public page by required phrases."""

from __future__ import annotations

import argparse
import ipaddress
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SKIPPED_URLS = {"unknown", "none", "-"}
BLOCKED_HOSTS = {"localhost"}
NOTE_RENDERED_BODY_HOSTS = {"note.com", "www.note.com"}
NOTE_BODY_FETCH_TIMEOUT_SECONDS = 45


def validate_public_http_url(url: str) -> tuple[bool, str | None]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False, "unsupported_url_scheme"
    if not parsed.hostname:
        return False, "missing_url_host"

    host = parsed.hostname.lower()
    if host in BLOCKED_HOSTS or host.endswith(".localhost"):
        return False, "local_host_blocked"

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True, None

    if address.is_private or address.is_loopback or address.is_link_local:
        return False, "private_or_local_ip_blocked"

    return True, None


def fetch_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": "note-publishing-suite-diff-check/0.1"})
    with urlopen(req, timeout=20) as res:
        data = res.read()
    return data.decode("utf-8", errors="replace")


def should_fetch_rendered_note_body(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in NOTE_RENDERED_BODY_HOSTS


def fetch_rendered_note_body(url: str) -> str:
    script = ROOT / "scripts" / "fetch_note_body.js"
    result = subprocess.run(
        ["node", str(script), url],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=NOTE_BODY_FETCH_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown_error"
        raise RuntimeError(f"rendered_note_body_fetch_failed: {detail}")
    return result.stdout.strip()


def fetch_page_text(url: str) -> tuple[str, str]:
    if should_fetch_rendered_note_body(url):
        return fetch_rendered_note_body(url), "rendered_note_body"
    return fetch_text(url), "raw_http_text"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("note_url")
    parser.add_argument("draft", type=Path)
    parser.add_argument("phrases", nargs="*")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.note_url.lower() in SKIPPED_URLS:
        result = {"overall": "skipped", "reason": "note_url_unknown", "checks": []}
    else:
        ok, reason = validate_public_http_url(args.note_url)
        if not ok:
            result = {
                "overall": "blocked",
                "reason": reason,
                "checks": [],
                "external_fetch_performed": False,
            }
        else:
            page, fetch_method = fetch_page_text(args.note_url)
            draft_text = args.draft.read_text(encoding="utf-8")
            phrases = args.phrases or [
                line.strip() for line in draft_text.splitlines() if len(line.strip()) >= 24
            ][:5]
            checks = [
                {"phrase": phrase, "in_draft": phrase in draft_text, "in_page": phrase in page}
                for phrase in phrases
            ]
            result = {
                "overall": "ok" if all(c["in_page"] for c in checks) else "warning",
                "checks": checks,
                "external_fetch_performed": True,
                "fetch_method": fetch_method,
            }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"overall={result['overall']}")
        for check in result.get("checks", []):
            print(f"in_page={check['in_page']} phrase={check['phrase'][:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
