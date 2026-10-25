#!/usr/bin/env python3
"""公開後のworkspace台帳更新。既定dry-run、外部送信なし。"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import json
import re
from pathlib import Path
import importlib.util
_LOADER_SPEC = importlib.util.spec_from_file_location(
    "_nps_loader_bootstrap", Path(__file__).with_name("nps_script_loader.py"))
if _LOADER_SPEC is None or _LOADER_SPEC.loader is None:
    raise ImportError("cannot load NPS script loader")
_LOADER_MODULE = importlib.util.module_from_spec(_LOADER_SPEC)
_LOADER_SPEC.loader.exec_module(_LOADER_MODULE)
_load_sibling_module = _LOADER_MODULE.load_script
atomic_write_bytes = _load_sibling_module("sync_note_public_snapshot").atomic_write_bytes
canonical_destination = _load_sibling_module("sync_note_public_snapshot").canonical_destination
durable_unlink = _load_sibling_module("sync_note_public_snapshot").durable_unlink
extract_note_id = _load_sibling_module("sync_note_public_snapshot").extract_note_id
ledger_file_lock = _load_sibling_module("sync_note_public_snapshot").ledger_file_lock
load_local_observation = _load_sibling_module("sync_note_public_snapshot").load_local_observation
reject_file_aliases = _load_sibling_module("sync_note_public_snapshot").reject_file_aliases
reject_package_outputs = _load_sibling_module("sync_note_public_snapshot").reject_package_outputs
resolve_workspace_root = _load_sibling_module("sync_note_public_snapshot").resolve_workspace_root
check_postpublish_review = _load_sibling_module("note_postpublish_review").check_postpublish_review
RuntimeVerifier = _load_sibling_module("note_postpublish_review").RuntimeVerifier

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
    published = canonical_destination(published)
    return published.with_name(f".{published.name}.publication-transaction.json")



def recover_transaction(published: Path, draft: Path) -> None:
    """両台帳lock保持中、既存journalをforward-completeする。"""
    published = canonical_destination(published)
    draft = canonical_destination(draft)
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
    published = canonical_destination(published)
    draft = canonical_destination(draft)
    journal = transaction_path(published)
    payload = {"schema": "note-ledger-transaction/v1", "published_path": str(published.resolve()),
               "draft_path": str(draft.resolve()), "published": published_rows, "drafts": draft_rows}
    atomic_write_bytes(journal, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    recover_transaction(published, draft)


def main(argv: list[str] | None = None, *, runtime_verifier: RuntimeVerifier | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--draft", required=True, type=Path)
    parser.add_argument("--title")
    parser.add_argument("--ledger-dir", type=Path)
    parser.add_argument("--note-id")
    parser.add_argument("--verified-at")
    parser.add_argument("--verification-status", default="published_or_scheduled_unverified", choices=["published_or_scheduled_unverified", "published_verified"])
    parser.add_argument("--published-snapshot")
    parser.add_argument("--workspace-root", type=Path, help="採用workspace。任意階層の台帳とarchive-pathを結線する場合に指定")
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
    parser.add_argument("--settings", type=Path, help="既存feedback保存先を解決するworkspace設定")
    parser.add_argument("--review-article-id", help="公開IDと異なる既存の制作記事ID。利用側の対応表で確認する")
    parser.add_argument("--review-source", type=Path, help="保全済み本人原文。原稿を自動修正しない")
    parser.add_argument("--review-prior", type=Path)
    parser.add_argument("--conversation-id")
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
    if args.write_ledger:
        targets = (canonical_destination(args.published_ledger), canonical_destination(args.draft_ledger))
        try:
            reject_package_outputs(list(targets), ROOT)
        except ValueError as exc:
            parser.error(f"{exc} --ledger-dir、または両台帳pathを明示してください")
        args.published_ledger, args.draft_ledger = targets
    if not args.draft.is_file():
        raise ValueError("原稿が存在しません")
    inputs = [args.draft]
    if args.local_observation:
        inputs.append(args.local_observation)
    if args.published_snapshot:
        inputs.append(Path(args.published_snapshot))
    if args.archive_path:
        workspace = resolve_workspace_root(args.published_ledger, args.workspace_root)
        inputs.append(workspace / args.archive_path)
    reject_file_aliases(inputs, [args.published_ledger, args.draft_ledger, transaction_path(args.published_ledger)])
    if args.published_body_sha256 is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", args.published_body_sha256):
        raise ValueError("published-body-sha256 は64桁のSHA-256が必要です")
    observed = load_local_observation(args.local_observation, args.url) if args.local_observation else None
    feedback_context = None
    if any(value is not None for value in (args.settings, args.review_source, args.review_prior, args.conversation_id, args.review_article_id)):
        if not args.settings or not args.review_source or not args.conversation_id:
            parser.error("feedback接続には--settings/--review-source/--conversation-idが必要です")
        read_workspace_settings = _load_sibling_module("note_workflow_gate").read_workspace_settings
        _, dirs = read_workspace_settings(args.settings, args.review_article_id or note_id)
        feedback_context = dict(dirs=dirs, source=args.review_source, draft=args.draft,
                                prior=args.review_prior or args.review_source, conversation_id=args.conversation_id,
                                article_id=args.review_article_id or note_id)
    postpublish_review = check_postpublish_review(observed,
        base_dir=args.local_observation.parent if args.local_observation else Path("."),
        runtime_verifier=runtime_verifier, feedback_context=feedback_context,
        write_feedback=args.write_ledger)
    changes = {"local_source": str(args.draft), "source": "note-publishing-suite",
               "plain_status": "published_observed" if observed else args.verification_status}
    if observed:
        changes["postpublication_check"] = {
            "status": postpublish_review["status"],
            "complete": postpublish_review["postpublication_complete"],
            "body_sha256": postpublish_review.get("body_sha256"),
            "checked_at": observed["captured_at"],
            "review_evidence_ref": observed.get("editorial_review", {}).get("evidence_ref"),
        }
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
        workspace = resolve_workspace_root(args.published_ledger, args.workspace_root)
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
                      "postpublish_review": postpublish_review,
                      "postpublication_complete": postpublish_review["postpublication_complete"],
                      "external_actions": []}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
