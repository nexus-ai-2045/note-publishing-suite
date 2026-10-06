#!/usr/bin/env python3
"""公開済みNote本文を来歴付きMarkdownとしてローカル保存する。"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import stat
import tempfile
import urllib.request
from urllib.parse import urlparse
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER_REL = Path("data") / "published_notes.json"
TRANSACTION_SUFFIX = ".snapshot-transaction.json"


class AtomicReplaceDurabilityError(OSError):
    """os.replace は完了したが、親directoryの永続化確認に失敗した。"""


def fsync_directory(path: Path) -> None:
    """rename/unlinkしたdirectory entryを電源断後も残す。"""
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_unlink(path: Path, *, missing_ok: bool = False) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        if not missing_ok:
            raise
        return
    fsync_directory(path.parent)


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """同一directory内でstageしてから置換し、途中内容をliveに見せない。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    target_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    try:
        with tempfile.NamedTemporaryFile(
            "wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.chmod(temp_path, target_mode)
        os.replace(temp_path, path)
        temp_path = None
        try:
            fsync_directory(path.parent)
        except OSError as exc:
            raise AtomicReplaceDurabilityError(
                f"置換後のdirectory fsyncに失敗しました: {path.parent}"
            ) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@contextmanager
def ledger_file_lock(ledger_path: Path):
    """ledger path単位のOS lock。crash時はOSが解放し、repo内にlockfileを残さない。"""
    lock_key = hashlib.sha256(str(ledger_path.resolve()).encode("utf-8")).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"note-public-snapshot-{lock_key}.lock"
    with lock_path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if handle.read(1) == b"":
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("published_notes ledger を別processが更新中です") from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("published_notes ledger を別processが更新中です") from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def extract_note_id(url: str) -> str:
    parsed = urlparse(url)
    match = re.fullmatch(r"/[^/]+/n/(n[A-Za-z0-9_-]+)", parsed.path.rstrip("/"))
    if parsed.scheme != "https" or parsed.netloc != "note.com" or match is None:
        raise ValueError(f"note URL が不正です: {url}")
    return match.group(1)


def load_local_observation(path: Path, url: str) -> dict:
    """内部ブラウザの公開現物読戻し。失敗時はネットワーク取得へ戻さない。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "note-public-observation/v1":
        raise ValueError("ローカル観測 schema が不正です")
    note_id = extract_note_id(url)
    if data.get("note_id") != note_id or data.get("url") != url:
        raise ValueError("ローカル観測 URL/note_id が対象と一致しません")
    for key in ("title", "body", "captured_at", "captured_by"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"ローカル観測 {key} が空または不正です")
    if data["captured_by"] != "codex-internal-browser":
        raise ValueError("ローカル観測の取得経路が内部ブラウザではありません")
    captured = datetime.fromisoformat(data["captured_at"].replace("Z", "+00:00"))
    if captured.tzinfo is None:
        raise ValueError("captured_at にtimezoneがありません")
    data["body"] = data["body"].strip()
    expected = data.get("body_sha256")
    actual = hashlib.sha256(data["body"].encode("utf-8")).hexdigest()
    if expected is not None and expected != actual:
        raise ValueError("ローカル観測本文 hash が一致しません")
    if "tags" in data and (not isinstance(data["tags"], list) or any(not isinstance(t, str) for t in data["tags"])):
        raise ValueError("ローカル観測 tags が不正です")
    return data


def resolve_ledger_path(explicit: Path | None) -> Path | None:
    """台帳 path を解決する。

    標準フローでは --ledger を省略しても wire_archive_path が走るよう、
    workspace の data/published_notes.json を既定候補にする。
    明示指定があればそれを優先し、候補が無ければ wire しない。
    """
    if explicit is not None:
        return explicit
    for candidate in (
        Path.cwd() / DEFAULT_LEDGER_REL,
        PACKAGE_ROOT / DEFAULT_LEDGER_REL,
    ):
        if candidate.is_file():
            return candidate
    return None


def archive_rel_path(ledger_path: Path, output: Path) -> str:
    """台帳に書く archive_path を repo 相対 POSIX 形式で返す。

    台帳は `<repo>/data/published_notes.json` に置く規約なので、その 2 つ上を
    repo root とみなす。Windows の区切りを台帳へ混ぜない。

    output が repo 外だと relative_to が ValueError になる。呼び出し側は
    ファイル書き込み前にこれを呼び、孤児ファイルを作らないこと。
    """
    repo_root = ledger_path.resolve().parents[1]
    try:
        return output.resolve().relative_to(repo_root).as_posix()
    except ValueError as exc:
        raise ValueError(
            f"output が台帳の repo root 外です: output={output.resolve()} "
            f"repo_root={repo_root}"
        ) from exc


def transaction_path(ledger_path: Path) -> Path:
    return ledger_path.with_name(f".{ledger_path.name}{TRANSACTION_SUFFIX}")


def recover_pending_transaction(ledger_path: Path, *, protected_inputs: list[Path] | None = None) -> bool:
    """中断したsnapshot/ledger同期をjournalからforward-completeする。lock保持中に呼ぶ。"""
    journal = transaction_path(ledger_path)
    if not journal.exists():
        return False
    payload = json.loads(journal.read_text(encoding="utf-8"))
    required = {
        "note_id", "archive_path", "title", "body_char_count", "body_sha256", "snapshot_text"
    }
    if not isinstance(payload, dict) or not required.issubset(payload):
        raise ValueError(f"snapshot transaction journal が不正です: {journal.name}")
    if payload.get("schema") != "note-public-snapshot-transaction/v1":
        raise ValueError(f"snapshot transaction schema が不正です: {journal.name}")
    for key in ("note_id", "archive_path", "title", "snapshot_text"):
        if not isinstance(payload[key], str) or not payload[key]:
            raise ValueError(f"snapshot transaction {key} が不正です: {journal.name}")
    if not isinstance(payload["body_char_count"], int) or payload["body_char_count"] < 0:
        raise ValueError(f"snapshot transaction body_char_count が不正です: {journal.name}")
    if not re.fullmatch(r"[0-9a-f]{64}", str(payload["body_sha256"])):
        raise ValueError(f"snapshot transaction body_sha256 が不正です: {journal.name}")

    snapshot_match = re.fullmatch(
        r"---\n(?P<frontmatter>.*?)\n---\n\n# (?P<title>[^\r\n]+)\n\n(?P<body>.*)\n",
        payload["snapshot_text"],
        re.DOTALL,
    )
    if snapshot_match is None:
        raise ValueError(f"snapshot transaction snapshot_text が不正です: {journal.name}")
    snapshot_body = snapshot_match.group("body")
    snapshot_hash = hashlib.sha256(snapshot_body.encode("utf-8")).hexdigest()
    frontmatter: dict[str, str] = {}
    for line in snapshot_match.group("frontmatter").splitlines():
        if ": " not in line:
            raise ValueError(f"snapshot transaction frontmatter が不正です: {journal.name}")
        key, value = line.split(": ", 1)
        if key in frontmatter:
            raise ValueError(f"snapshot transaction frontmatter key が重複しています: {key}")
        frontmatter[key] = value
    try:
        frontmatter_title = json.loads(frontmatter["title"])
        frontmatter_url = json.loads(frontmatter["source_url"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"snapshot transaction frontmatter のtitle/source_urlが不正です: {journal.name}"
        ) from exc
    if not isinstance(frontmatter_title, str) or not isinstance(frontmatter_url, str):
        raise ValueError(f"snapshot transaction frontmatter の型が不正です: {journal.name}")
    try:
        frontmatter_note_id = extract_note_id(frontmatter_url)
    except ValueError as exc:
        raise ValueError(f"snapshot transaction source_url が不正です: {journal.name}") from exc
    if (
        snapshot_match.group("title") != payload["title"]
        or frontmatter_title != payload["title"]
        or frontmatter_note_id != payload["note_id"]
        or frontmatter.get("schema_version") != "note-public-snapshot/v1"
        or frontmatter.get("source_kind") != "public_note"
        or len(snapshot_body) != payload["body_char_count"]
        or snapshot_hash != payload["body_sha256"]
        or frontmatter.get("body_sha256") != snapshot_hash
    ):
        raise ValueError(f"snapshot transaction metadata がsnapshotと一致しません: {journal.name}")

    repo_root = ledger_path.resolve().parents[1]
    output = repo_root / str(payload["archive_path"])
    expected_rel = archive_rel_path(ledger_path, output)
    if expected_rel != payload["archive_path"]:
        raise ValueError(f"snapshot transaction archive_path が不正です: {journal.name}")
    reject_file_aliases(protected_inputs or [], [output, ledger_path, journal])
    ensure_ledger_row(ledger_path, str(payload["note_id"]))

    atomic_write_bytes(output, str(payload["snapshot_text"]).encode("utf-8"))
    wire_public_snapshot_metadata(
        ledger_path,
        str(payload["note_id"]),
        expected_rel,
        title=str(payload["title"]),
        body_char_count=payload["body_char_count"],
        body_sha256=str(payload["body_sha256"]),
        _lock_held=True,
    )
    durable_unlink(journal)
    return True


def wire_public_snapshot_metadata(
    ledger_path: Path,
    note_id: str,
    archive_rel: str,
    *,
    title: str | None = None,
    body_char_count: int | None = None,
    body_sha256: str | None = None,
    _lock_held: bool = False,
) -> None:
    """台帳の該当行へ公開現物由来の snapshot metadata を原子的に書く。

    行の選択は note_id の完全一致だけで行う。人が目で行を選ぶと隣の行へ
    書き込む事故が起きるため (実例: MPC のパスが Public Readiness の行に
    入っていた)、スナップショットを作ったのと同じ URL から導出した note_id
    でしか行を特定しない。

    該当行が無い / 複数ある場合は書かずに失敗させる。DB の外部キー制約に
    相当する振る舞いで、黙って通すと不整合がそのまま残る。
    """
    if not _lock_held:
        with ledger_file_lock(ledger_path):
            wire_public_snapshot_metadata(
                ledger_path,
                note_id,
                archive_rel,
                title=title,
                body_char_count=body_char_count,
                body_sha256=body_sha256,
                _lock_held=True,
            )
        return

    rows = json.loads(ledger_path.read_text(encoding="utf-8"))
    row = _require_single_row(rows, note_id, ledger_path)
    updates = {"archive_path": archive_rel}
    if title is not None:
        updates["title"] = title
    if body_char_count is not None:
        updates["body_char_count"] = body_char_count
    if body_sha256 is not None:
        updates["public_body_sha256"] = body_sha256
    if all(row.get(key) == value for key, value in updates.items()):
        return
    row.update(updates)
    payload = (json.dumps(rows, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    atomic_write_bytes(ledger_path, payload)


def wire_archive_path(ledger_path: Path, note_id: str, archive_rel: str) -> None:
    """後方互換 wrapper。新規処理は公開metadataをまとめて結線する。"""
    wire_public_snapshot_metadata(ledger_path, note_id, archive_rel)


def _require_single_row(rows: list[dict], note_id: str, ledger_path: Path) -> dict:
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("台帳はJSON objectの配列である必要があります")
    matches = [row for row in rows if row.get("note_id") == note_id]
    if not matches:
        raise ValueError(f"台帳に note_id={note_id} の行が無い: {ledger_path}")
    if len(matches) > 1:
        raise ValueError(f"台帳に note_id={note_id} の行が {len(matches)} 件ある: {ledger_path}")
    row = matches[0]
    if row.get("url") and extract_note_id(row["url"]) != note_id:
        raise ValueError("台帳のURL/note_idが一致しません")
    return row


def ensure_ledger_row(ledger_path: Path, note_id: str) -> None:
    """取得前に台帳の行を確認する。

    取得・ファイル書き込みの後で落ちると、台帳に繋がらないファイルだけが
    残って孤児になる。繋げないと分かった時点で何も作らずに止める。
    """
    _require_single_row(json.loads(ledger_path.read_text(encoding="utf-8")), note_id, ledger_path)


def fetch_published_data(url: str) -> dict:
    """公開APIの生 data を返す。更新後照合など呼び出し側が状態を判定する。"""
    request = urllib.request.Request(
        f"https://note.com/api/v3/notes/{extract_note_id(url)}",
        headers={"Accept": "application/json", "User-Agent": "note-public-snapshot/1"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    return payload["data"]


def extract_published_text(data: dict) -> str:
    """公開API data から本文テキストを取り出す。"""
    if data.get("status") != "published":
        raise ValueError("note記事がpublishedではありません")
    body = str(data.get("body") or "")
    text = re.sub(r"<br\s*/?>", "\n", body, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|h[1-6]|li|blockquote)>", "\n", text, flags=re.IGNORECASE)
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def fetch_published_note(url: str) -> dict[str, str]:
    data = fetch_published_data(url)
    title = str(data.get("name") or "").strip()
    body = extract_published_text(data)
    if not title:
        raise ValueError("note記事の公開タイトルが空です")
    return {"title": title, "body": body}


def fetch_published_text(url: str) -> str:
    """後方互換 wrapper。公開現物の本文だけを返す。"""
    return fetch_published_note(url)["body"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="公開済みNote本文のローカルsnapshotを作る")
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--title",
        help="互換用の期待タイトル。保存値は note 公開APIのタイトルを正本とする",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-draft", required=True)
    parser.add_argument(
        "--ledger",
        type=Path,
        default=None,
        help=(
            "published_notes.json。省略時は workspace の data/published_notes.json "
            "を自動解決し、該当行の archive_path を自動で繋ぐ"
        ),
    )
    parser.add_argument("--local-observation", type=Path, help="内部ブラウザの公開現物JSON。指定時はネットワーク取得しない")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write-ledger", action="store_true", help="snapshotと台帳を実更新する")
    return parser


def reject_file_aliases(inputs: list[Path], outputs: list[Path]) -> None:
    """resolveとhardlinkの両方を検査し、入力・別出力の置換を拒否する。"""
    def same(left: Path, right: Path) -> bool:
        return left.resolve() == right.resolve() or (left.exists() and right.exists() and left.samefile(right))
    for index, output in enumerate(outputs):
        if any(same(output, other) for other in inputs + outputs[:index]):
            raise ValueError("原稿・証跡・snapshotと台帳・journalは別ファイルにしてください")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    note_id = extract_note_id(args.url)
    ledger = resolve_ledger_path(args.ledger)
    source_draft = Path(args.source_draft)
    inputs = [source_draft] + ([args.local_observation] if args.local_observation else [])
    outputs = [args.output] + ([ledger, transaction_path(ledger)] if ledger else [])
    reject_file_aliases(inputs, outputs)

    # 取得・書き込みの前に結線可否を確定する。後で落ちると孤児ファイルが残る。
    archive_path = None
    if ledger is not None:
        ensure_ledger_row(ledger, note_id)
        archive_path = archive_rel_path(ledger, args.output)

    if not source_draft.is_file():
        raise ValueError("source-draft が存在しません")
    if args.output.resolve() == source_draft.resolve() or (args.output.exists() and args.output.samefile(source_draft)):
        raise ValueError("公開snapshotと原稿は別ファイルにしてください")
    published = load_local_observation(args.local_observation, args.url) if args.local_observation else fetch_published_note(args.url)
    title = published["title"]
    body = published["body"]
    body_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()
    captured_at = published.get("captured_at") or datetime.now(timezone.utc).isoformat()
    text = "\n".join(
        [
            "---",
            "schema_version: note-public-snapshot/v1",
            f"title: {quote(title)}",
            f"source_url: {quote(args.url)}",
            f"source_draft: {quote(args.source_draft)}",
            f"captured_at: {quote(captured_at)}",
            f"captured_by: {published.get('captured_by', 'codex')}",
            "source_kind: public_note",
            f"body_sha256: {body_sha256}",
            "external_action: none",
            "---",
            "",
            f"# {title}",
            "",
            body.strip(),
            "",
        ]
    )
    if not args.write_ledger:
        print(json.dumps({"status": "dry-run", "output": str(args.output), "note_id": note_id,
                          "archive_path": archive_path, "title": title, "body_char_count": len(body),
                          "public_body_sha256": body_sha256, "captured_at": captured_at,
                          "snapshot_text": text, "external_actions": []}, ensure_ascii=False, indent=2))
        return 0
    if ledger is not None and archive_path is not None:
        with ledger_file_lock(ledger):
            recover_pending_transaction(ledger, protected_inputs=inputs)
            previous_output = args.output.read_bytes() if args.output.exists() else None
            output_written = False
            ledger_committed = False
            journal = transaction_path(ledger)
            try:
                ensure_ledger_row(ledger, note_id)
                transaction = {
                    "schema": "note-public-snapshot-transaction/v1",
                    "note_id": note_id,
                    "archive_path": archive_path,
                    "title": title,
                    "body_char_count": len(body),
                    "body_sha256": body_sha256,
                    "snapshot_text": text,
                }
                atomic_write_bytes(
                    journal,
                    (json.dumps(transaction, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
                )
                atomic_write_bytes(args.output, text.encode("utf-8"))
                output_written = True
                wire_public_snapshot_metadata(
                    ledger,
                    note_id,
                    archive_path,
                    title=title,
                    body_char_count=len(body),
                    body_sha256=body_sha256,
                    _lock_held=True,
                )
                ledger_committed = True
                durable_unlink(journal)
            except Exception as exc:
                if ledger_committed or isinstance(exc, AtomicReplaceDurabilityError):
                    # snapshot と ledger は既に同じ新版。journal を残せば次回の
                    # recover が冪等に再適用して cleanup できる。replace後の
                    # durability failureも書込み済みとして扱い、journalを消さない。
                    raise
                if output_written:
                    if previous_output is None:
                        durable_unlink(args.output, missing_ok=True)
                    else:
                        atomic_write_bytes(args.output, previous_output)
                durable_unlink(journal, missing_ok=True)
                raise
    else:
        atomic_write_bytes(args.output, text.encode("utf-8"))

    print(json.dumps({"status": "ok", "output": str(args.output), "note_id": note_id, "archive_path": archive_path, "title": title, "requested_title_matched": args.title is None or args.title == title, "body_char_count": len(body), "public_body_sha256": body_sha256, "captured_at": captured_at, "external_actions": []}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
