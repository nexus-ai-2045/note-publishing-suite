#!/usr/bin/env python3
"""公開後のworkspace台帳更新。既定dry-run、外部送信なし。"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import json
import re
from pathlib import Path
from sync_note_public_snapshot import atomic_write_bytes, durable_unlink, extract_note_id, ledger_file_lock, load_local_observation, reject_file_aliases

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED_LEDGER = ROOT / "data" / "published_notes.json"
DRAFT_LEDGER = ROOT / "data" / "note_drafts.json"


def load_list(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"台帳はobjectの配列である必要があります: {path}")
    return rows


def write_list(path: Path, rows: list[dict]) -> None:
    atomic_write_bytes(path, (json.dumps(rows, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def upsert(rows: list[dict], note_id: str, url: str, changes: dict) -> dict:
    matches = [row for row in rows if row.get("note_id") == note_id or row.get("url") == url]
    if len(matches) > 1:
        raise ValueError(f"台帳に対象記事が重複しています: {note_id}")
    if matches:
        row = matches[0]
        if row.get("note_id") not in (None, note_id) or (row.get("url") and extract_note_id(row["url"]) != note_id):
            raise ValueError("台帳のURL/note_idが一致しません")
    else:
        row = {}
        rows.append(row)
    row.update({"note_id": note_id, "url": url, **changes})
    return row


def transaction_path(published: Path) -> Path:
    return published.with_name(f".{published.name}.publication-transaction.json")



def recover_transaction(published: Path, draft: Path) -> None:
    """両台帳lock保持中、既存journalをforward-completeする。"""
    journal = transaction_path(published)
    if not journal.exists():
        return
    payload = json.loads(journal.read_text(encoding="utf-8"))
    if (not isinstance(payload, dict) or payload.get("schema") != "note-ledger-transaction/v1"
            or payload.get("published_path") != str(published.resolve())
            or payload.get("draft_path") != str(draft.resolve())):
        raise ValueError("公開台帳transactionの接続先が不正です")
    for key in ("published", "drafts"):
        rows = payload.get(key)
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("公開台帳transactionの内容が不正です")
    write_list(published, payload["published"])
    write_list(draft, payload["drafts"])
    durable_unlink(journal)


def commit_ledgers(published: Path, draft: Path, published_rows: list[dict], draft_rows: list[dict]) -> None:
    journal = transaction_path(published)
    payload = {"schema": "note-ledger-transaction/v1", "published_path": str(published.resolve()),
               "draft_path": str(draft.resolve()), "published": published_rows, "drafts": draft_rows}
    atomic_write_bytes(journal, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    recover_transaction(published, draft)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--draft", required=True, type=Path)
    parser.add_argument("--title")
    parser.add_argument("--ledger-dir", type=Path)
    parser.add_argument("--note-id")
    parser.add_argument("--verified-at")
    parser.add_argument("--verification-status", default="published_or_scheduled_unverified", choices=["published_or_scheduled_unverified", "published_verified"])
    parser.add_argument("--published-snapshot")
    parser.add_argument("--archive-path", help="公開snapshotのworkspace相対path。両台帳へ同値を結線")
    parser.add_argument("--published-body-sha256")
    parser.add_argument("--local-draft-differs-from-published", action="store_true")
    parser.add_argument("--cover-image-verified", action="store_true")
    parser.add_argument("--published-at")
    parser.add_argument("--tags")
    parser.add_argument("--image-url")
    parser.add_argument("--published-ledger", type=Path, default=PUBLISHED_LEDGER)
    parser.add_argument("--draft-ledger", type=Path, default=DRAFT_LEDGER)
    parser.add_argument("--local-observation", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write-ledger", action="store_true")
    args = parser.parse_args(argv)
    try:
        note_id = extract_note_id(args.url)
    except ValueError as exc:
        parser.error(str(exc))
    args.url = args.url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    if args.note_id and args.note_id != note_id:
        parser.error("--note-id does not match URL")
    if args.verification_status == "published_verified" and not args.verified_at:
        parser.error("--verified-at is required for published_verified")
    if args.ledger_dir:
        if args.published_ledger != PUBLISHED_LEDGER or args.draft_ledger != DRAFT_LEDGER:
            parser.error("--ledger-dir cannot be combined with explicit ledger paths")
        args.published_ledger = args.ledger_dir / "published_notes.json"
        args.draft_ledger = args.ledger_dir / "note_drafts.json"
    if not args.draft.is_file():
        raise ValueError("原稿が存在しません")
    inputs = [args.draft]
    if args.local_observation:
        inputs.append(args.local_observation)
    if args.published_snapshot:
        inputs.append(Path(args.published_snapshot))
    if args.archive_path:
        inputs.append(args.published_ledger.resolve().parents[1] / args.archive_path)
    reject_file_aliases(inputs, [args.published_ledger, args.draft_ledger, transaction_path(args.published_ledger)])
    if args.published_body_sha256 is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", args.published_body_sha256):
        raise ValueError("published-body-sha256 は64桁のSHA-256が必要です")
    observed = load_local_observation(args.local_observation, args.url) if args.local_observation else None
    changes = {"local_source": str(args.draft), "source": "note-publishing-suite",
               "plain_status": "published_observed" if observed else args.verification_status}
    if observed:
        changes.update(title=observed["title"], public_observed_at=observed["captured_at"],
                       public_observation_route=observed["captured_by"])
        if "tags" in observed:
            changes["tags"] = observed["tags"]
    elif args.title:
        changes["title"] = args.title
    if args.published_at:
        changes["published_at"] = args.published_at
    for name in ("verified_at", "published_snapshot", "published_body_sha256"):
        if getattr(args, name) is not None:
            changes[name] = getattr(args, name)
    if args.verification_status == "published_verified":
        changes["verification_source"] = "operator_cli_claim" if not observed else "local_observation"
    if args.cover_image_verified:
        changes["cover_image_verified"] = True
    if args.local_draft_differs_from_published:
        changes["local_draft_differs_from_published"] = True
    if args.tags is not None:
        changes["tags"] = [t.strip() for t in args.tags.split(",") if t.strip()]
    if args.archive_path is not None:
        workspace = args.published_ledger.resolve().parents[1]
        archive = (workspace / args.archive_path).resolve()
        try:
            archive.relative_to(workspace)
        except ValueError:
            raise ValueError("archive-path がworkspace外です")
        if not archive.is_file():
            raise ValueError("archive-path のsnapshotが存在しません")
        changes["archive_path"] = archive.relative_to(workspace).as_posix()
    if args.image_url is not None:
        changes["image_url"] = args.image_url
    with ExitStack() as stack:
        if args.write_ledger:
            for path in sorted((args.published_ledger, args.draft_ledger), key=lambda p: str(p.resolve())):
                stack.enter_context(ledger_file_lock(path))
        if transaction_path(args.published_ledger).exists():
            if not args.write_ledger:
                raise ValueError("未完了transactionがあります。接続先を確認して --write-ledger で復旧してください")
            recover_transaction(args.published_ledger, args.draft_ledger)
        published, drafts = load_list(args.published_ledger), load_list(args.draft_ledger)
        entry = upsert(published, note_id, args.url, changes)
        entry.setdefault("published_at", None)
        draft_changes = {"draft": str(args.draft), "status": "published_from_note_editor_record" if observed or args.verification_status == "published_verified" else "publication_unverified"}
        if args.archive_path is not None:
            draft_changes["archive_path"] = entry["archive_path"]
        if entry.get("title"):
            draft_changes["published_title"] = entry["title"]
        upsert(drafts, note_id, args.url, draft_changes)
        if args.write_ledger:
            commit_ledgers(args.published_ledger, args.draft_ledger, published, drafts)
    print(json.dumps({"mode": "write-ledger" if args.write_ledger else "dry-run", "published_entry": entry,
                      "updated_ledgers": [str(args.published_ledger), str(args.draft_ledger)] if args.write_ledger else [],
                      "external_actions": []}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
