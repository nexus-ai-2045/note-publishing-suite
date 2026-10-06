#!/usr/bin/env python3
"""Apply remaining Note editor actions via Orca eval. Never publish.

Safety contracts (review-clear):
- Require expected note identity / account args and match read-only fresh state
  before any mutation.
- Never auto-cardify an existing URL paragraph. Embed only when an empty
  paragraph selection anchor is verified; otherwise stop at manual_boundary.
- Aggregate postconditions and return non-zero when any requested operation
  is unconfirmed or failed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIRECTORY = str(Path(__file__).resolve().parent)
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)
from note_workflow_gate import check_packet, load_packet

FORBIDDEN_BUTTONS = ("投稿する", "公開する", "予約投稿", "更新する")
EMBED_SUCCESS = frozenset({"ok", "skip"})
EMBED_FAILURE = frozenset(
    {
        "nomenu",
        "nop",
        "lostmenu",
        "nota",
        "fail",
        "manual_boundary",
        "no_empty_paragraph",
        "selection_not_empty",
    }
)
NOTE_ID_RE = re.compile(r"/notes/(n[0-9a-zA-Z]+)")


def is_forbidden_button(label: str) -> bool:
    return label in FORBIDDEN_BUTTONS


def has_figure_exact(url: str, have: list[str]) -> bool:
    needle = (url or "").rstrip("/")
    return any((item or "").rstrip("/") == needle for item in have)


def remaining_url_paragraphs(paragraphs: list[str], figure_srcs: list[str]) -> list[str]:
    have = {(item or "").rstrip("/") for item in figure_srcs}
    seen: set[str] = set()
    leftover: list[str] = []
    for raw in paragraphs:
        url = (raw or "").strip()
        if not url.startswith("http"):
            continue
        key = url.rstrip("/")
        if key in have or key in seen:
            continue
        seen.add(key)
        leftover.append(url)
    return leftover


def click_rect_is_visible(rect: dict, margin: int = 40) -> bool:
    inner_h = int(rect.get("innerH") or 0)
    y = int(rect.get("y") or -1)
    return inner_h > 0 and margin <= y <= inner_h - margin


def extract_note_id(url: str) -> str:
    match = NOTE_ID_RE.search(url or "")
    return match.group(1) if match else ""


def preflight_errors(observed: dict[str, Any], expected: dict[str, str]) -> list[str]:
    """Compare read-only page identity with caller-fixed expectations."""
    errors: list[str] = []
    note_id = str(observed.get("note_id") or extract_note_id(str(observed.get("url") or "")))
    url = str(observed.get("url") or "")
    title = str(observed.get("title") or "")
    account = str(observed.get("account") or "")

    expect_note_id = expected.get("note_id") or ""
    expect_url = expected.get("url") or ""
    expect_title = expected.get("title") or ""
    expect_account = expected.get("account") or ""

    if not expect_note_id:
        errors.append("expect_note_id_required")
    elif not note_id:
        errors.append("observed_note_id_missing")
    elif note_id != expect_note_id:
        errors.append(f"note_id_mismatch: observed={note_id} expected={expect_note_id}")

    if expect_url and expect_url not in url:
        errors.append(f"url_mismatch: observed={url!r} expected_contains={expect_url!r}")

    if expect_title and expect_title not in title:
        errors.append(f"title_mismatch: observed={title!r} expected_contains={expect_title!r}")

    if expect_account and expect_account != account:
        errors.append(
            f"account_mismatch: observed={account!r} expected={expect_account!r}"
        )

    return errors


def selection_is_empty_paragraph(state: dict[str, Any]) -> bool:
    """True only when caret is collapsed inside an empty paragraph block."""
    if not isinstance(state, dict):
        return False
    if state.get("collapsed") is not True:
        return False
    if int(state.get("selectionLength") or 0) != 0:
        return False
    text = str(state.get("anchorText") or state.get("blockText") or "").strip()
    if text:
        return False
    tag = str(state.get("blockTag") or "").lower()
    if tag and tag not in {"p", "paragraph", "div"}:
        return False
    if state.get("insideContentEditable") is False:
        return False
    return True


def embed_status_ok(status: str) -> bool:
    return status in EMBED_SUCCESS


def toc_ok(toc: Any) -> bool:
    if not isinstance(toc, dict):
        return False
    if toc.get("status") == "already":
        return True
    observed = toc.get("observed")
    if isinstance(observed, dict) and observed.get("n") == 1:
        return True
    return False


def tags_ok(tags: Any) -> bool:
    if not isinstance(tags, dict):
        return False
    opened = tags.get("opened")
    if isinstance(opened, dict) and opened.get("ok") is False:
        return False
    if tags.get("forbidden_clicked") is True:
        return False
    added = tags.get("added") or []
    if not added:
        return False
    return all("no_tag_field" not in str(item) for item in added)


def save_ok(save: Any) -> bool:
    return isinstance(save, dict) and save.get("ok") is True


def collect_failures(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if report.get("preflight_errors"):
        failures.extend(f"preflight:{item}" for item in report["preflight_errors"])
    embeds = report.get("embeds") or {}
    for url, status in embeds.items():
        if not embed_status_ok(str(status)):
            failures.append(f"embed:{status}:{url}")
    if report.get("toc") is not None and not toc_ok(report.get("toc")):
        failures.append("toc_unconfirmed")
    if report.get("tags") is not None and not tags_ok(report.get("tags")):
        failures.append("tags_unconfirmed")
    if report.get("save") is not None and not save_ok(report.get("save")):
        failures.append("save_unconfirmed")
    return failures


def run_orca(args: list[str], timeout: int = 40) -> dict:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "stdout": proc.stdout[:400], "stderr": proc.stderr[:400]}


def eval_js(orca: str, page: str, expr: str) -> object:
    data = run_orca([orca, "eval", "--page", page, "--expression", expr, "--json"])
    result = (data.get("result") or {}).get("result")
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return result
    return result


def click_label(orca: str, page: str, label: str) -> dict:
    if is_forbidden_button(label):
        return {"ok": False, "error": "forbidden_button", "label": label}
    payload = json.dumps(label, ensure_ascii=False)
    return eval_js(
        orca,
        page,
        f"""(()=>{{const b=[...document.querySelectorAll("button")].find(x=>((x.innerText||"").trim()==={payload})||((x.getAttribute("aria-label")||"")==={payload})); if(!b) return JSON.stringify({{ok:false,label:{payload}}}); b.click(); return JSON.stringify({{ok:true}});}})()""",
    ) or {"ok": False}


def figures(orca: str, page: str) -> list[str]:
    value = eval_js(
        orca,
        page,
        'JSON.stringify([...document.querySelectorAll("figure[data-src]")].map(f=>f.getAttribute("data-src")||""))',
    )
    return value if isinstance(value, list) else []


def read_card_state(orca: str, page: str, url: str) -> dict[str, Any]:
    """Read one URL's card, raw paragraph, and ordinary-link state."""
    target = json.dumps(url, ensure_ascii=False)
    value = eval_js(
        orca,
        page,
        f'''(()=>{{const url={target};
          const figs=[...document.querySelectorAll('figure[embedded-service][data-src]')]
            .filter(f=>f.getAttribute('data-src')===url);
          const raw=[...document.querySelectorAll('[contenteditable="true"] p')]
            .filter(p=>(p.innerText||'').trim()===url);
          const links=[...document.querySelectorAll('[contenteditable="true"] a[href]')]
            .filter(a=>a.getAttribute('href')===url);
          return JSON.stringify({{url:location.href,figures:figs.length,
            services:figs.map(f=>f.getAttribute('embedded-service')),
            raw_paragraphs:raw.length,ordinary_links:links.length}});
        }})()''',
    )
    return value if isinstance(value, dict) else {}


def card_state_ok(state: dict[str, Any], expected_note_id: str) -> bool:
    return (
        extract_note_id(str(state.get("url") or "")) == expected_note_id
        and state.get("figures") == 1
        and len(state.get("services") or []) == 1
        and state.get("raw_paragraphs") == 0
        and state.get("ordinary_links") == 0
    )


def verify_card_after_enter(
    orca: str, page: str, url: str, expected_note_id: str, timeout_seconds: float = 12.0
) -> dict[str, Any]:
    """Bounded readback for Note's asynchronous URL-to-card conversion."""
    deadline = time.monotonic() + timeout_seconds
    samples = 0
    while True:
        state = read_card_state(orca, page, url)
        samples += 1
        if card_state_ok(state, expected_note_id):
            return {"url": url, "status": "ok", "samples": samples, "observed_at": datetime.now(timezone.utc).isoformat(), "observed": state}
        if extract_note_id(str(state.get("url") or "")) != expected_note_id:
            return {"url": url, "status": "note_identity_mismatch", "samples": samples, "observed_at": datetime.now(timezone.utc).isoformat(), "observed": state}
        if state.get("figures", 0) > 1:
            return {"url": url, "status": "duplicate_card", "samples": samples, "observed_at": datetime.now(timezone.utc).isoformat(), "observed": state}
        if time.monotonic() >= deadline:
            return {"url": url, "status": "conversion_unconfirmed", "samples": samples, "observed_at": datetime.now(timezone.utc).isoformat(), "observed": state}
        time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))


def has_figure(url: str, have: list[str]) -> bool:
    return has_figure_exact(url, have)


def has_menu(orca: str, page: str) -> bool:
    value = eval_js(
        orca,
        page,
        'JSON.stringify({ok:!![...document.querySelectorAll("button")].find(b=>(b.getAttribute("aria-label")||"")==="メニューを開く")})',
    )
    return isinstance(value, dict) and value.get("ok") is True


def read_page_identity(orca: str, page: str) -> dict[str, Any]:
    value = eval_js(
        orca,
        page,
        """(()=>{
          const url = location.href || "";
          const title = document.title || "";
          const m = url.match(/\\/notes\\/(n[0-9a-zA-Z]+)/);
          const noteId = m ? m[1] : "";
          const accountEl = document.querySelector('[data-name], a[href*="note.com/"] img[alt], header img[alt]');
          const account = (accountEl && (accountEl.getAttribute("data-name") || accountEl.getAttribute("alt"))) || "";
          const body = (document.body && document.body.innerText) || "";
          return JSON.stringify({url, title, note_id: noteId, account, body_sample: body.slice(0, 200)});
        })()""",
    )
    return value if isinstance(value, dict) else {}


def read_selection_state(orca: str, page: str) -> dict[str, Any]:
    value = eval_js(
        orca,
        page,
        """(()=>{
          const sel = window.getSelection();
          if (!sel || sel.rangeCount < 1) {
            return JSON.stringify({collapsed:false, selectionLength:0, insideContentEditable:false, anchorText:"", blockText:"", blockTag:""});
          }
          const anchor = sel.anchorNode;
          const el = anchor && (anchor.nodeType === 1 ? anchor : anchor.parentElement);
          const block = el && el.closest ? el.closest("p, h1, h2, h3, li, div[data-node], [contenteditable=true] p") : null;
          const editable = !!(el && el.closest && el.closest("[contenteditable=true]"));
          const blockText = block ? (block.innerText || "").trim() : "";
          const anchorText = (sel.toString() || "").trim();
          return JSON.stringify({
            collapsed: !!sel.isCollapsed,
            selectionLength: (sel.toString() || "").length,
            insideContentEditable: editable,
            anchorText,
            blockText,
            blockTag: block ? (block.tagName || "").toLowerCase() : ""
          });
        })()""",
    )
    return value if isinstance(value, dict) else {}


def focus_empty_paragraph(orca: str, page: str) -> dict[str, Any]:
    """Click the first empty contenteditable paragraph. Never click a URL row."""
    rect = eval_js(
        orca,
        page,
        """(()=>{
          const paras = [...document.querySelectorAll("[contenteditable=true] p")];
          const empty = paras.find(p => {
            const t = (p.innerText || "").trim();
            return !t && !p.querySelector("figure, iframe, img, a[href]");
          });
          if (!empty) return JSON.stringify({err:"no_empty_paragraph"});
          empty.scrollIntoView({block:"center"});
          let r = empty.getBoundingClientRect();
          if (r.top < 40 || r.bottom > window.innerHeight - 40) {
            document.documentElement.scrollBy(0, r.top - window.innerHeight / 2);
            r = empty.getBoundingClientRect();
          }
          return JSON.stringify({
            x: Math.round(r.x + Math.min(36, Math.max(8, r.width / 2))),
            y: Math.round(r.y + Math.max(4, r.height / 2)),
            top: r.top,
            innerH: window.innerHeight,
            ok: true
          });
        })()""",
    )
    if not isinstance(rect, dict) or rect.get("err"):
        return {"ok": False, "error": (rect or {}).get("err", "no_empty_paragraph")}
    if not click_rect_is_visible(rect):
        return {"ok": False, "error": "empty_paragraph_not_visible"}
    run_orca([orca, "mouse", "move", "--x", str(rect["x"]), "--y", str(rect["y"]), "--page", page, "--json"])
    run_orca([orca, "mouse", "down", "--button", "left", "--page", page, "--json"])
    run_orca([orca, "mouse", "up", "--button", "left", "--page", page, "--json"])
    time.sleep(0.2)
    state = read_selection_state(orca, page)
    if selection_is_empty_paragraph(state):
        return {"ok": True, "selection": state}
    return {"ok": False, "error": "selection_not_empty", "selection": state}


def restore_menu(orca: str, page: str) -> bool:
    click_label(orca, page, "埋め込みをやめる")
    eval_js(
        orca,
        page,
        """(()=>{const h=[...document.querySelectorAll("h2")].find(x=>x.innerText.trim()==="入口") || document.querySelector("h2"); if(!h) return JSON.stringify({ok:false}); h.scrollIntoView({block:"center"}); return JSON.stringify({ok:true});})()""",
    )
    rect = eval_js(
        orca,
        page,
        """(()=>{const h=[...document.querySelectorAll("h2")].find(x=>x.innerText.trim()==="入口") || document.querySelector("h2"); if(!h) return JSON.stringify({err:1}); const r=h.getBoundingClientRect(); return JSON.stringify({x:Math.round(r.x+24), y:Math.round(r.y+8), top:r.top, innerH:window.innerHeight});})()""",
    )
    if not isinstance(rect, dict) or "x" not in rect:
        return has_menu(orca, page)
    if not click_rect_is_visible(rect):
        return has_menu(orca, page)
    run_orca([orca, "mouse", "move", "--x", str(rect["x"]), "--y", str(rect["y"]), "--page", page, "--json"])
    run_orca([orca, "mouse", "down", "--button", "left", "--page", page, "--json"])
    run_orca([orca, "mouse", "up", "--button", "left", "--page", page, "--json"])
    time.sleep(0.25)
    return has_menu(orca, page)


def embed_url(orca: str, page: str, url: str) -> str:
    """Embed via empty-paragraph selection + 埋め込み dialog. Never click existing URL rows."""
    have = figures(orca, page)
    if has_figure(url, have):
        return "skip"

    focused = focus_empty_paragraph(orca, page)
    if not focused.get("ok"):
        err = str(focused.get("error") or "manual_boundary")
        if err in EMBED_FAILURE:
            return err
        return "manual_boundary"

    if not has_menu(orca, page) and not restore_menu(orca, page):
        return "nomenu"

    # Re-verify selection after menu restore; do not proceed on a URL row.
    if not selection_is_empty_paragraph(read_selection_state(orca, page)):
        refocus = focus_empty_paragraph(orca, page)
        if not refocus.get("ok"):
            return "manual_boundary"

    click_label(orca, page, "メニューを開く")
    time.sleep(0.45)
    clicked = click_label(orca, page, "埋め込み")
    if isinstance(clicked, dict) and clicked.get("ok") is False:
        return "nop"
    time.sleep(0.4)
    payload = json.dumps(url)
    set_val = eval_js(
        orca,
        page,
        f"""(()=>{{const ta=[...document.querySelectorAll("textarea")].find(t=>t.placeholder==="https://example.com"); if(!ta) return JSON.stringify({{err:"nota"}}); const proto=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value"); proto.set.call(ta,{payload}); ta.dispatchEvent(new Event("input",{{bubbles:true}})); ta.dispatchEvent(new Event("change",{{bubbles:true}})); return JSON.stringify({{val:ta.value}});}})()""",
    )
    if not isinstance(set_val, dict) or not str(set_val.get("val", "")).startswith("http"):
        click_label(orca, page, "埋め込みをやめる")
        return "nota"
    click_label(orca, page, "適用")
    for _ in range(6):
        time.sleep(1.0)
        if has_figure(url, figures(orca, page)):
            return "ok"
    click_label(orca, page, "埋め込みをやめる")
    return "fail"


def insert_toc(orca: str, page: str) -> dict:
    existing = eval_js(
        orca,
        page,
        'JSON.stringify({n:document.querySelectorAll("table-of-contents").length})',
    )
    if isinstance(existing, dict) and existing.get("n") == 1:
        return {"ok": True, "status": "already"}
    if not has_menu(orca, page):
        restore_menu(orca, page)
    click_label(orca, page, "メニューを開く")
    time.sleep(0.45)
    clicked = click_label(orca, page, "目次")
    time.sleep(0.7)
    observed = eval_js(
        orca,
        page,
        'JSON.stringify({n:document.querySelectorAll("table-of-contents").length, toc:[...document.querySelectorAll("table-of-contents")].map(e=>e.getAttribute("toc"))})',
    )
    return {"click": clicked, "observed": observed}


def add_tags(orca: str, page: str, tags: list[str]) -> dict:
    """Open publish settings, add tags, never press 投稿する."""
    opened = click_label(orca, page, "公開に進む")
    time.sleep(1.2)
    state = eval_js(
        orca,
        page,
        'JSON.stringify({url:location.href, title:document.title, labels:[...document.querySelectorAll("button")].map(b=>(b.innerText||"").trim()).filter(Boolean).slice(0,40), inputs:[...document.querySelectorAll("input,textarea")].map(i=>({ph:i.placeholder, type:i.type, name:i.name})).slice(0,30)})',
    )
    added: list[str] = []
    for tag in tags:
        field = eval_js(
            orca,
            page,
            f"""(()=>{{const el=[...document.querySelectorAll("input,textarea")].find(i=>/タグ|ハッシュ/.test((i.placeholder||"")+(i.name||"")+(i.getAttribute("aria-label")||""))); if(!el) return JSON.stringify({{err:"no_tag_field"}}); el.focus(); const proto=Object.getOwnPropertyDescriptor(el.tagName==="TEXTAREA"?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,"value"); proto.set.call(el,{json.dumps(tag)}); el.dispatchEvent(new Event("input",{{bubbles:true}})); el.dispatchEvent(new KeyboardEvent("keydown",{{key:"Enter",bubbles:true}})); el.dispatchEvent(new KeyboardEvent("keyup",{{key:"Enter",bubbles:true}})); return JSON.stringify({{ok:true, val:el.value}});}})()""",
        )
        added.append(str(field))
        time.sleep(0.25)
    after = eval_js(
        orca,
        page,
        'JSON.stringify({labels:[...document.querySelectorAll("button")].map(b=>(b.innerText||"").trim()).filter(Boolean).slice(0,50), text:(document.body.innerText||"").slice(0,1200)})',
    )
    forbidden_clicked = False
    return {
        "opened": opened,
        "state": state,
        "added": added,
        "after": after,
        "forbidden_clicked": forbidden_clicked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Note editor embeds/TOC/tags. Never publish.")
    parser.add_argument("--orca", default="/Applications/Orca.app/Contents/Resources/bin/orca")
    parser.add_argument("--page", required=True)
    parser.add_argument(
        "--expect-note-id",
        required=True,
        help="Expected note id (n...). Must match read-only page state before mutations.",
    )
    parser.add_argument("--expect-url", default="", help="Substring that must appear in location.href")
    parser.add_argument("--expect-title", default="", help="Substring that must appear in document.title")
    parser.add_argument("--expect-account", default="", help="Exact account label observed on the page")
    parser.add_argument("--urls-file", help="JSON array of remaining URLs to embed via empty-paragraph dialog")
    parser.add_argument(
        "--verify-card-urls-file",
        help="Read-only check after the operator pastes each standalone URL and presses Enter",
    )
    parser.add_argument("--card-receipt-path", help="New local JSON file for the card readback receipt")
    parser.add_argument("--tags", nargs="*", default=[])
    parser.add_argument("--toc", action="store_true")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--nps-settings", type=Path, help="runtimeが選択したpackage外のSSOT設定")
    parser.add_argument("--workflow-packet", type=Path, help="版ごとの人間承認packet")
    parser.add_argument("--conversation-id", help="runtimeが独立に取得した現在会話ID")
    args = parser.parse_args()
    if args.verify_card_urls_file and (args.urls_file or args.tags or args.toc or args.save):
        parser.error("--verify-card-urls-file must be run separately from editor mutations")
    if args.card_receipt_path and not args.verify_card_urls_file:
        parser.error("--card-receipt-path requires --verify-card-urls-file")

    report: dict[str, Any] = {
        "publication_actions_performed": [],
        "embeds": {},
        "toc": None,
        "tags": None,
        "save": None,
        "figures": [],
        "preflight_errors": [],
        "failures": [],
        "manual_boundary": False,
    }

    approved_urls = []
    # 承認なしではread-only preflightにも進まず、外部操作を開始しない。
    if args.urls_file or args.tags or args.toc or args.save:
        gate_errors = []
        if not args.workflow_packet or not args.conversation_id or not args.nps_settings:
            gate_errors.append("修正前後の人間承認packet・現在会話ID・外部SSOT設定が必要です")
        else:
            try:
                packet = load_packet(args.workflow_packet)
                approved_urls = json.loads(Path(args.urls_file).read_text(encoding="utf-8")) if args.urls_file else []
            except (OSError, ValueError, UnicodeError):
                packet = None
                gate_errors.append("承認packetまたはURL計画が読取不能・不正です")
            approval = check_packet(packet, "edit", args.conversation_id, args.workflow_packet.resolve().parent, settings_path=args.nps_settings)
            report["workflow_gate"] = approval
            if approval["status"] != "approved":
                gate_errors.extend(approval["reasons"])
            else:
                actual_plan = {"urls": approved_urls, "tags": args.tags, "toc": args.toc, "save": args.save}
                if packet.get("edit_plan") != actual_plan:
                    gate_errors.append("実行する操作が承認済みのedit_planと一致しません")
                if packet.get("article_id") != args.expect_note_id:
                    gate_errors.append("承認対象の記事が実行対象と一致しません")
                settings = packet.get("settings")
                if not args.expect_account or not isinstance(settings, dict) or settings.get("account") != args.expect_account:
                    gate_errors.append("承認対象の名義が実行対象と一致しません")
        if gate_errors:
            report["preflight_errors"] = gate_errors
            report["failures"] = gate_errors
            report["manual_boundary"] = True
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1

    observed = read_page_identity(args.orca, args.page)
    report["observed"] = observed
    expected = {
        "note_id": args.expect_note_id,
        "url": args.expect_url,
        "title": args.expect_title,
        "account": args.expect_account,
    }
    report["expected"] = expected
    errors = preflight_errors(observed, expected)
    report["preflight_errors"] = errors
    if errors:
        report["failures"] = collect_failures(report)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("preflight_failed\t" + ";".join(errors), flush=True)
        return 1

    if args.verify_card_urls_file:
        urls = json.loads(Path(args.verify_card_urls_file).read_text(encoding="utf-8"))
        report["card_receipts"] = []
        for url in urls:
            receipt = verify_card_after_enter(args.orca, args.page, url, args.expect_note_id)
            report["card_receipts"].append(receipt)
            if receipt["status"] != "ok":
                report["failures"].append(f"card:{receipt['status']}:{url}")
                break
        if args.card_receipt_path:
            with Path(args.card_receipt_path).open("x", encoding="utf-8") as output:
                json.dump(report, output, ensure_ascii=False, indent=2)
                output.write("\n")
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            for receipt in report["card_receipts"]:
                print(f"{receipt['status']}\t{receipt['url']}")
        return 1 if report["failures"] else 0

    if args.urls_file:
        urls = approved_urls
        for url in urls:
            status = embed_url(args.orca, args.page, url)
            report["embeds"][url] = status
            if status == "manual_boundary" or status == "no_empty_paragraph" or status == "selection_not_empty":
                report["manual_boundary"] = True
            print(f"{status}\t{url}", flush=True)
            if not embed_status_ok(status):
                # Stop further embeds after the first unconfirmed/failed attempt.
                break
    if args.toc:
        report["toc"] = insert_toc(args.orca, args.page)
        print(f"toc\t{json.dumps(report['toc'], ensure_ascii=False)}", flush=True)
    if args.tags:
        report["tags"] = add_tags(args.orca, args.page, args.tags)
        print(f"tags\t{json.dumps(report['tags'], ensure_ascii=False)[:1000]}", flush=True)
    if args.save:
        report["save"] = click_label(args.orca, args.page, "下書き保存")
        print(f"save\t{report['save']}", flush=True)
    report["figures"] = figures(args.orca, args.page)
    report["failures"] = collect_failures(report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
