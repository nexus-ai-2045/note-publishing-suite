#!/usr/bin/env python3
"""Note下書きをリポジトリ外へ検証可能な形で退避・復元する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "note-draft-durability/v1"
ALLOWED_SUFFIXES = {".md", ".html"}
ALLOWED_REASONS = {"before_edit", "after_edit", "before_editor", "manual"}
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


class BoundaryError(RuntimeError):
    """安全境界により操作を拒否した。"""


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _same_lexical_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(_lexical_absolute(left))) == os.path.normcase(
        str(_lexical_absolute(right))
    )


def _is_reparse(stat_result: os.stat_result) -> bool:
    return bool(
        getattr(stat_result, "st_file_attributes", 0)
        & FILE_ATTRIBUTE_REPARSE_POINT
    )


def _reject_reparse_chain(root: Path, target: Path, *, include_target: bool = True) -> None:
    root = _lexical_absolute(root)
    target = _lexical_absolute(target)
    if not _is_within(target, root):
        raise BoundaryError("blob_outside_backup_namespace")
    current = root
    relative = target.relative_to(root)
    components = [Path("."), *relative.parents[::-1]]
    if include_target:
        components.append(relative)
    for component in components:
        candidate = current if component == Path(".") else root / component
        try:
            observed = candidate.lstat()
        except OSError as exc:
            raise BoundaryError("blob_path_component_unreadable") from exc
        if stat.S_ISLNK(observed.st_mode) or _is_reparse(observed):
            raise BoundaryError("blob_reparse_point_not_allowed")


def _read_stable_regular_file(path: Path, *, backup_root: Path) -> bytes:
    _reject_reparse_chain(backup_root, path)
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or _is_reparse(before):
                raise BoundaryError("blob_not_regular_file")
            data = stream.read()
            after = os.fstat(stream.fileno())
        current = path.lstat()
    except BoundaryError:
        raise
    except OSError as exc:
        raise BoundaryError("blob_unreadable") from exc
    identity_before = (before.st_dev, before.st_ino)
    identity_after = (after.st_dev, after.st_ino)
    identity_current = (current.st_dev, current.st_ino)
    observed_before = (before.st_size, before.st_mtime_ns)
    observed_after = (after.st_size, after.st_mtime_ns)
    observed_current = (current.st_size, current.st_mtime_ns)
    if (
        identity_before != identity_after
        or identity_before != identity_current
        or observed_before != observed_after
        or observed_before != observed_current
        or len(data) != before.st_size
        or stat.S_ISLNK(current.st_mode)
        or _is_reparse(current)
    ):
        raise BoundaryError("blob_changed_during_read")
    return data


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_common_dir(repo_root: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    common = Path(result.stdout.strip())
    if not common.is_absolute():
        common = repo_root / common
    return _resolved(common)


def _repo_identity(repo_root: Path) -> tuple[str, str]:
    common = _git_common_dir(repo_root)
    identity = common or _resolved(repo_root)
    return (
        hashlib.sha256(str(identity).casefold().encode("utf-8")).hexdigest()[:16],
        str(identity),
    )


def _worktree_id(repo_root: Path) -> str:
    return hashlib.sha256(str(_resolved(repo_root)).casefold().encode("utf-8")).hexdigest()[:16]


def default_backup_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise BoundaryError("LOCALAPPDATA is unavailable; pass --backup-root")
    return Path(local) / "nexus-ai" / "draft-history"


def _atomic_write(path: Path, data: bytes) -> None:
    """既存shared atomic_writeと同じ tmp→fsync→replace 契約。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd: int | None = None
    temporary: str | None = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".tmp_", dir=path.parent)
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if fd is not None:
            os.close(fd)
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def _atomic_create_new(path: Path, data: bytes) -> None:
    """内容を完全に書いた一時fileを、既存targetを置換せず公開する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd: int | None = None
    temporary: str | None = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".tmp_restore_", dir=path.parent)
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise BoundaryError("existing_destination_restore_not_supported") from exc
    finally:
        if fd is not None:
            os.close(fd)
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def _validate_source(source: Path, *, repo_root: Path, allow_empty: bool) -> tuple[bytes, os.stat_result]:
    if not source.is_file():
        raise BoundaryError("source_missing_or_not_file")
    if source.suffix.lower() not in ALLOWED_SUFFIXES:
        raise BoundaryError("source_suffix_not_allowed")
    try:
        data = _read_stable_regular_file(source, backup_root=repo_root)
        after = source.lstat()
    except BoundaryError as exc:
        raise BoundaryError("source_changed_or_unsafe_during_snapshot") from exc
    if not data and not allow_empty:
        raise BoundaryError("empty_source_requires_allow_empty")
    return data, after


def _paths(source: Path, backup_root: Path, repo_root: Path, digest: str) -> tuple[Path, Path]:
    root = _resolved(backup_root) / _repo_identity(repo_root)[0]
    suffix = source.suffix.lower()
    blob = root / "blobs" / f"{digest}{suffix}"
    source_id = hashlib.sha256(str(source).casefold().encode("utf-8")).hexdigest()[:12]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    receipt = root / "receipts" / f"{source_id}-{stamp}-{time.time_ns()}-{digest[:12]}.json"
    return blob, receipt


def snapshot(
    draft: Path,
    backup_root: Path,
    *,
    reason: str,
    repo_root: Path,
    allow_empty: bool = False,
) -> dict[str, Any]:
    source = _lexical_absolute(draft)
    repo = _resolved(repo_root)
    backup = _resolved(backup_root)
    if reason not in ALLOWED_REASONS:
        raise BoundaryError("reason_not_allowed")
    if not _is_within(source, repo):
        raise BoundaryError("source_must_be_inside_repo")
    if _is_within(backup, repo):
        raise BoundaryError("backup_root_must_be_outside_repo")
    data, observed = _validate_source(source, repo_root=repo, allow_empty=allow_empty)
    digest = _sha256(data)
    blob, receipt = _paths(source, backup, repo, digest)

    blob.parent.mkdir(parents=True, exist_ok=True)
    blob_lexically_exists = os.path.lexists(blob)
    _reject_reparse_chain(backup, blob, include_target=blob_lexically_exists)
    if blob.exists():
        if _sha256(_read_stable_regular_file(blob, backup_root=backup)) != digest:
            raise BoundaryError("existing_blob_hash_mismatch")
    else:
        _atomic_write(blob, data)
    if _sha256(_read_stable_regular_file(blob, backup_root=backup)) != digest:
        raise BoundaryError("blob_hash_mismatch_after_write")

    try:
        relative = source.relative_to(repo).as_posix()
    except ValueError:
        relative = None
    repo_id, common_dir = _repo_identity(repo)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "verified",
        "source": str(source),
        "source_relative": relative,
        "repo_id": repo_id,
        "repo_common_dir": common_dir,
        "worktree_root": str(repo),
        "worktree_id": _worktree_id(repo),
        "blob": str(blob),
        "receipt": str(receipt),
        "sha256": digest,
        "bytes": len(data),
        "mtime_ns": observed.st_mtime_ns,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "privacy": "local_only",
        "tool_version": SCHEMA_VERSION,
    }
    receipt_data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt_lexically_exists = os.path.lexists(receipt)
    _reject_reparse_chain(backup, receipt, include_target=receipt_lexically_exists)
    _atomic_create_new(receipt, receipt_data)
    return payload


def _load_receipt(receipt: Path) -> dict[str, Any]:
    receipt = _lexical_absolute(receipt)
    try:
        raw = _read_stable_regular_file(receipt, backup_root=receipt.parent.parent.parent)
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, BoundaryError) as exc:
        raise BoundaryError("receipt_unreadable") from exc
    if not isinstance(payload, dict):
        raise BoundaryError("receipt_schema_invalid")
    required = {
        "schema_version", "source", "source_relative", "repo_id",
        "repo_common_dir", "worktree_root", "worktree_id", "blob",
        "receipt", "sha256", "bytes",
    }
    string_fields = required - {"bytes", "source_relative"}
    valid_strings = all(isinstance(payload.get(name), str) for name in string_fields)
    valid_hash = (
        isinstance(payload.get("sha256"), str)
        and len(payload["sha256"]) == 64
        and all(character in "0123456789abcdef" for character in payload["sha256"])
    )
    valid_bytes = isinstance(payload.get("bytes"), int) and payload["bytes"] >= 0
    valid_relative = payload.get("source_relative") is None or isinstance(payload.get("source_relative"), str)
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or not required.issubset(payload)
        or not valid_strings
        or not valid_hash
        or not valid_bytes
        or not valid_relative
    ):
        raise BoundaryError("receipt_schema_invalid")
    if Path(payload["receipt"]).resolve(strict=False) != receipt.resolve(strict=False):
        raise BoundaryError("receipt_path_mismatch")
    receipt_path = _lexical_absolute(receipt)
    source_suffix = Path(payload["source"]).suffix.lower()
    if source_suffix not in ALLOWED_SUFFIXES:
        raise BoundaryError("receipt_blob_path_mismatch")
    namespace = receipt_path.parent.parent
    expected_namespace = namespace.parent / payload["repo_id"]
    expected_blob = namespace / "blobs" / f"{payload['sha256']}{source_suffix}"
    if (
        receipt_path.parent.name != "receipts"
        or namespace != expected_namespace
        or not _same_lexical_path(Path(payload["blob"]), expected_blob)
    ):
        raise BoundaryError("receipt_blob_path_mismatch")
    return payload


def verify(receipt: Path) -> dict[str, Any]:
    payload = _load_receipt(receipt)
    blob = Path(payload["blob"])
    if not blob.is_file():
        return {**payload, "status": "failed", "error": "blob_missing", "next_action": "別のreceiptまたは外部バックアップを確認"}
    data = _read_stable_regular_file(blob, backup_root=_lexical_absolute(receipt).parent.parent.parent)
    if len(data) != payload["bytes"] or _sha256(data) != payload["sha256"]:
        return {**payload, "status": "failed", "error": "blob_hash_mismatch", "next_action": "このblobを復元に使わない"}
    return {**payload, "status": "verified", "error": None}


def _receipts_for(draft: Path, backup_root: Path, repo_root: Path, *, same_relative: bool = False) -> list[Path]:
    source = str(_resolved(draft))
    root = _resolved(backup_root) / _repo_identity(repo_root)[0] / "receipts"
    try:
        relative = _resolved(draft).relative_to(_resolved(repo_root)).as_posix()
    except ValueError:
        relative = None
    matches: list[Path] = []
    for receipt in root.glob("*.json") if root.is_dir() else []:
        try:
            payload = _load_receipt(receipt)
            if payload.get("source") == source or (
                same_relative and relative is not None and payload.get("source_relative") == relative
            ):
                matches.append(receipt)
        except BoundaryError:
            continue
    return sorted(matches, key=lambda item: item.name, reverse=True)


def status(draft: Path, backup_root: Path, *, repo_root: Path) -> dict[str, Any]:
    source = _resolved(draft)
    related = _receipts_for(source, backup_root, repo_root, same_relative=True)
    other_sources: set[str] = set()
    for item in related:
        payload = _load_receipt(item)
        candidate_text = payload["source"]
        if candidate_text == str(source) or verify(item)["status"] != "verified":
            continue
        candidate = Path(candidate_text)
        if (
            candidate.is_file()
            and not candidate.is_symlink()
            and _sha256(_read_stable_regular_file(candidate, backup_root=candidate.parent)) == payload["sha256"]
        ):
            other_sources.add(candidate_text)
    other_sources_sorted = sorted(other_sources)
    if other_sources_sorted:
        return {
            "status": "found_in_other_worktree",
            "covered": False,
            "source": str(source),
            "other_worktree_sources": other_sources_sorted,
            "next_action": "別worktreeの実在と内容を確認してから回収方針を決める",
        }
    receipts = _receipts_for(source, backup_root, repo_root)
    if not receipts:
        return {"status": "uncovered", "covered": False, "source": str(source), "next_action": "snapshotを作成"}
    checked = verify(receipts[0])
    if checked["status"] != "verified":
        return {**checked, "covered": False}
    if not source.exists():
        return {**checked, "status": "missing", "covered": True, "next_action": "検証済みreceiptから別pathへ復元"}
    current = _sha256(_read_stable_regular_file(source, backup_root=source.parent))
    if current != checked["sha256"]:
        return {**checked, "status": "stale", "covered": True, "current_sha256": current, "next_action": "現在版のsnapshotを作成"}
    return {**checked, "status": "current", "covered": True, "current_sha256": current}


def restore(
    receipt: Path,
    destination: Path,
    *,
    expected_current_sha256: str | None = None,
    restore_missing_original: bool = False,
) -> dict[str, Any]:
    checked = verify(receipt)
    if checked["status"] != "verified":
        raise BoundaryError(checked.get("error", "receipt_not_verified"))
    target = _lexical_absolute(destination)
    original = _resolved(Path(checked["source"]))
    if target.exists():
        # Windowsで他processの非協調書込みと安全なCASを保証できないため、
        # 初期版は既存fileへの復元を常に拒否する。
        raise BoundaryError("existing_destination_restore_not_supported")
    elif target == original and not restore_missing_original:
        raise BoundaryError("missing_original_requires_explicit_restore")
    target.parent.mkdir(parents=True, exist_ok=True)
    target_lexically_exists = os.path.lexists(target)
    _reject_reparse_chain(Path(target.anchor), target, include_target=target_lexically_exists)
    data = _read_stable_regular_file(
        Path(checked["blob"]), backup_root=_lexical_absolute(receipt).parent.parent.parent
    )
    _atomic_create_new(target, data)
    if _sha256(_read_stable_regular_file(target, backup_root=Path(target.anchor))) != checked["sha256"]:
        raise BoundaryError("restored_hash_mismatch")
    return {**checked, "status": "restored", "destination": str(target)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    common.add_argument("--backup-root", type=Path)
    common.add_argument("--repo-root", type=Path, required=True)
    snap = sub.add_parser("snapshot", parents=[common])
    snap.add_argument("--draft", type=Path, required=True)
    snap.add_argument("--reason", choices=sorted(ALLOWED_REASONS), required=True)
    snap.add_argument("--allow-empty", action="store_true")
    stat = sub.add_parser("status", parents=[common])
    stat.add_argument("--draft", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("--receipt", type=Path, required=True)
    check.add_argument("--json", action="store_true")
    recover = sub.add_parser("restore")
    recover.add_argument("--receipt", type=Path, required=True)
    recover.add_argument("--to", type=Path, required=True)
    recover.add_argument("--expected-current-sha256")
    recover.add_argument("--restore-missing-original", action="store_true")
    recover.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "snapshot":
            result = snapshot(args.draft, args.backup_root or default_backup_root(), reason=args.reason, repo_root=args.repo_root, allow_empty=args.allow_empty)
        elif args.command == "status":
            result = status(args.draft, args.backup_root or default_backup_root(), repo_root=args.repo_root)
        elif args.command == "verify":
            result = verify(args.receipt)
        else:
            result = restore(args.receipt, args.to, expected_current_sha256=args.expected_current_sha256, restore_missing_original=args.restore_missing_original)
    except BoundaryError as exc:
        result = {"status": "blocked", "error": str(exc), "next_action": "入力と安全境界を確認"}
        code = 3
    except OSError as exc:
        result = {"status": "failed", "error": type(exc).__name__, "next_action": "保存先と権限を確認"}
        code = 4
    else:
        code = 0 if result["status"] in {"verified", "current", "restored"} else 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if getattr(args, "json", False) else f"{result['status']}: {result.get('source', result.get('destination', ''))}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
