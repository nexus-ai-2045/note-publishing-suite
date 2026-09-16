#!/usr/bin/env python3
"""noteエディター向けの、本人・端末別同意を必須とするOSクリップボード経路。

すべての公開操作は期限付きローカル同意を検査してからmacOSコマンドを呼ぶ。
標準入力や--yesでの同意発行はできない。ファイルダイアログは開かない。
snapshot/restoreはテキストだけで、画像などの元データ復元を保証しない。
このゲートは運用上の事前確認であり、同じOS権限でコードやreceiptを編集
できる主体に対する認証sandboxではない。本人の承認を他の利用者へ配布しない。
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import getpass
import hashlib
import json
import math
import os
import platform
import plistlib
import time
import subprocess
import sys
import stat
from contextlib import contextmanager
import uuid
from pathlib import Path
from xml.parsers.expat import ExpatError


class ClipboardBridgeError(RuntimeError):
    """Raised when a clipboard subprocess call fails."""


CONSENT_VERSION = 1
MAX_CONSENT_SECONDS = 24 * 60 * 60
CONSENT_ACTIONS = frozenset(
    {"put_text", "put_image", "get_text", "snapshot", "restore"}
)
CONSENT_PHRASE = "OSクリップボードの読み書きと上書きを承認します"


def _consent_path(consent_path: str | Path | None = None) -> Path:
    return (
        Path(consent_path)
        if consent_path is not None
        else Path.home() / ".note-publishing-suite" / "clipboard-consent.json"
    )


def _device_id() -> str:
    # ホスト名は複数端末で一致するため使わない。対応済みmacOSのOS提供UUIDに限定する。
    if platform.system() != "Darwin":
        raise ClipboardBridgeError("対応する端末識別子を確認できません")
    try:
        result = subprocess.run(
            ["/usr/sbin/ioreg", "-a", "-r", "-d", "1", "-c", "IOPlatformExpertDevice"],
            check=True,
            capture_output=True,
            timeout=5,
        )
        entries = plistlib.loads(result.stdout)
        identifiers = [entry["IOPlatformUUID"] for entry in entries]
        if len(identifiers) != 1 or not isinstance(identifiers[0], str):
            raise ValueError("invalid device identifier")
        identifier = uuid.UUID(identifiers[0])
        if identifier.int in (0, (1 << 128) - 1):
            raise ValueError("invalid device identifier")
        return f"macos-ioplatformuuid:{identifier}"
    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
        KeyError,
        TypeError,
        plistlib.InvalidFileException,
        ExpatError,
    ):
        raise ClipboardBridgeError("対応する端末識別子を確認できません") from None


def _principal() -> dict[str, str]:
    # 運用上の本人・端末束縛。コード/同意ファイルを編集できる主体への認証sandboxではない。
    user = getpass.getuser()
    uid = str(os.getuid()) if hasattr(os, "getuid") else user
    machine = _device_id()
    if not user or not machine:
        raise ClipboardBridgeError("同意対象のユーザー・端末を確認できません")
    return {
        "user": hashlib.sha256(f"{user}:{uid}".encode()).hexdigest(),
        "machine": hashlib.sha256(machine.encode()).hexdigest(),
    }


def _require_consent(action: str, consent_path: str | Path | None = None) -> None:
    try:
        receipt = _read_receipt(_consent_path(consent_path))
        now = time.time()
        issued = receipt["issued_at"]
        expires = receipt["expires_at"]
        valid = (
            type(receipt["version"]) is int
            and receipt["version"] == CONSENT_VERSION
            and receipt["principal"] == _principal()
            and receipt["revoked"] is False
            and receipt["confirmation"] == "interactive-typed"
            and type(issued) in (int, float)
            and type(expires) in (int, float)
            and math.isfinite(issued)
            and math.isfinite(expires)
            and issued <= now < expires
            and 0 < expires - issued <= MAX_CONSENT_SECONDS
            and isinstance(receipt["actions"], list)
            and all(
                isinstance(item, str) and item in CONSENT_ACTIONS
                for item in receipt["actions"]
            )
            and action in receipt["actions"]
        )
    except (OSError, ValueError, KeyError, TypeError):
        valid = False
    if not valid:
        raise ClipboardBridgeError(
            "有効な本人・端末別同意がありません。consent-grantで事前確認してください"
        )


def _validate_darwin_acl(fd: int) -> None:
    if platform.system() != "Darwin":
        return
    # Apple sys/acl.h: EXTENDED=0x100, FIRST=0, NEXT=-1, EXTENDED_DENY=2。
    # pathnameではなく既に検査中のfdから取得し、既存ACLを変更しない。
    try:
        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        libc.acl_get_fd_np.argtypes = [ctypes.c_int, ctypes.c_int]
        libc.acl_get_fd_np.restype = ctypes.c_void_p
        libc.acl_valid.argtypes = [ctypes.c_void_p]
        libc.acl_valid.restype = ctypes.c_int
        libc.acl_get_entry.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        libc.acl_get_entry.restype = ctypes.c_int
        libc.acl_get_tag_type.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        libc.acl_get_tag_type.restype = ctypes.c_int
        libc.acl_free.argtypes = [ctypes.c_void_p]
        libc.acl_free.restype = ctypes.c_int
        acl = libc.acl_get_fd_np(fd, 0x100)
        if not acl:
            raise ValueError
        try:
            if libc.acl_valid(acl) != 0:
                raise ValueError
            entry = ctypes.c_void_p()
            entry_id = 0
            for _ in range(129):  # Apple ACL_MAX_ENTRIES=128 + 終端検査
                ctypes.set_errno(0)
                result = libc.acl_get_entry(acl, entry_id, ctypes.byref(entry))
                if result == -1 and ctypes.get_errno() == errno.EINVAL:
                    return
                if result != 0 or not entry.value:
                    raise ValueError
                tag = ctypes.c_int()
                if (
                    libc.acl_get_tag_type(entry, ctypes.byref(tag)) != 0
                    or tag.value != 2
                ):
                    # homeのdeny delete等は許可。allowは読取だけでも保守的に拒否。
                    raise ValueError
                entry_id = -1
            raise ValueError
        finally:
            libc.acl_free(acl)
    except (OSError, AttributeError, ValueError):
        raise ClipboardBridgeError("同意ファイルのACLを安全と確認できません") from None


def _validate_storage_fd(fd: int, *, directory: bool, private: bool = True) -> None:
    _validate_storage_stat(os.fstat(fd), directory=directory, private=private)
    _validate_darwin_acl(fd)


def _validate_storage_stat(info, *, directory: bool, private: bool = True) -> None:
    uid = os.getuid()
    correct_type = (
        stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    )
    if not correct_type or info.st_uid not in ({uid} if private else {0, uid}):
        raise ClipboardBridgeError("同意ファイルの所有者・種別を確認できません")
    forbidden = 0o077 if private else 0o022
    # root所有のsticky一時ディレクトリでは他利用者による子の置換はできない。
    sticky_root = (
        directory and not private and info.st_uid == 0 and info.st_mode & stat.S_ISVTX
    )
    if info.st_mode & forbidden and not sticky_root:
        raise ClipboardBridgeError("同意ファイルの保存権限が安全ではありません")
    if not directory and info.st_nlink != 1:
        raise ClipboardBridgeError("同意ファイルのリンクを許可できません")


@contextmanager
def _receipt_parent(path: Path, *, create: bool = False):
    # ACLを検査できないWindowsでは発行も読取も拒否する。POSIXはdir_fdで置換競合を防ぐ。
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise ClipboardBridgeError("同意ファイルの保存権限を確認できないOSです")
    path = path.absolute()
    if ".." in path.parts:
        raise ClipboardBridgeError("同意ファイルの保存先を確認できません")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    try:
        _validate_storage_fd(fd, directory=True, private=False)
        parts = path.parent.parts[1:]
        for index, part in enumerate(parts):
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
            _validate_storage_fd(fd, directory=True, private=index == len(parts) - 1)
        if not parts:
            _validate_storage_fd(fd, directory=True)
        yield fd, path.name
    finally:
        os.close(fd)


@contextmanager
def _receipt_stream(path: Path, *, write: bool = False):
    with _receipt_parent(path, create=write) as (parent, name):
        flags = os.O_WRONLY | os.O_CREAT if write else os.O_RDONLY
        # FIFO/deviceを読まず、symlinkを追わず、検査前に既存ファイルをtruncateしない。
        fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent)
        try:
            _validate_storage_fd(fd, directory=False)
            if write:
                os.ftruncate(fd, 0)
            stream = os.fdopen(fd, "w" if write else "r", encoding="utf-8")
        except BaseException:
            os.close(fd)
            raise
        with stream:
            yield stream


def _read_receipt(path: Path) -> dict:
    with _receipt_stream(path) as stream:
        return json.load(stream)


def _write_receipt(path: Path, receipt: dict) -> None:
    with _receipt_stream(path, write=True) as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)


def _grant_consent(path: Path, actions: list[str], hours: float) -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ClipboardBridgeError("同意は本人が対話端末で入力する必要があります")
    if not math.isfinite(hours) or not 0 < hours <= 24:
        raise ClipboardBridgeError("同意期限は0時間超・24時間以内です")
    print(
        "PC共通クリップボードの読取・上書きを許可します。元の画像などは復元保証がなく、snapshot/restoreはテキストだけです。"
    )
    print(f"許可操作: {', '.join(actions)} / 有効時間: {hours}")
    print(f"本人が次の文を入力してください: {CONSENT_PHRASE}")
    try:
        answer = input()
    except EOFError:
        answer = ""
    if answer != CONSENT_PHRASE:
        raise ClipboardBridgeError("同意が確認できないため停止しました")
    now = time.time()
    _write_receipt(
        path,
        {
            "version": CONSENT_VERSION,
            "principal": _principal(),
            "issued_at": now,
            "expires_at": now + hours * 3600,
            "revoked": False,
            "confirmation": "interactive-typed",
            "actions": actions,
        },
    )


def _put_text(text: str) -> None:
    try:
        subprocess.run(
            ["pbcopy"], input=text, text=True, check=True, capture_output=True
        )
    except (subprocess.CalledProcessError, OSError):
        raise ClipboardBridgeError("pbcopyの実行に失敗しました") from None


def put_text(text: str, *, consent_path: str | Path | None = None) -> None:
    _require_consent("put_text", consent_path)
    _put_text(text)


def put_image(path: str | Path, *, consent_path: str | Path | None = None) -> None:
    _require_consent("put_image", consent_path)
    image_path = Path(path)
    if not image_path.is_file():
        raise ClipboardBridgeError("画像ファイルを確認できません")
    escaped_path = str(image_path.resolve()).replace("\\", "\\\\").replace('"', '\\"')
    script = (
        f'set the clipboard to (read (POSIX file "{escaped_path}") as «class PNGf»)'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script], check=True, capture_output=True, text=True
        )
    except (subprocess.CalledProcessError, OSError):
        raise ClipboardBridgeError("画像のクリップボード書込に失敗しました") from None


def _get_text() -> str:
    try:
        result = subprocess.run(["pbpaste"], check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, OSError):
        raise ClipboardBridgeError("pbpasteの実行に失敗しました") from None
    return result.stdout


def get_text(*, consent_path: str | Path | None = None) -> str:
    _require_consent("get_text", consent_path)
    return _get_text()


def snapshot(*, consent_path: str | Path | None = None) -> str:
    """テキストのみ保存する。画像等の完全バックアップではない。"""
    _require_consent("snapshot", consent_path)
    return _get_text()


def restore(previous_text: str, *, consent_path: str | Path | None = None) -> None:
    _require_consent("restore", consent_path)
    _put_text(previous_text)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clipboard_bridge.py",
        description=(
            "Clipboard bridge CLI for note editor text/image entry. "
            "Never opens a file picker; OS clipboard only."
        ),
    )
    parser.add_argument("--consent-path", help="本人・端末別のローカル同意ファイル")
    subparsers = parser.add_subparsers(dest="command", required=True)

    put_text_parser = subparsers.add_parser(
        "put-text", help="Place text on the clipboard from a file."
    )
    put_text_parser.add_argument(
        "--file", required=True, help="Path to a text file to copy."
    )

    put_image_parser = subparsers.add_parser(
        "put-image", help="Place a PNG image on the clipboard from a file."
    )
    put_image_parser.add_argument(
        "--file", required=True, help="Path to a PNG file to copy."
    )

    subparsers.add_parser("get-text", help="Print current clipboard text.")

    restore_parser = subparsers.add_parser(
        "restore", help="Restore clipboard text from a snapshot file."
    )
    restore_parser.add_argument(
        "--file", required=True, help="Path to a text file with the snapshot."
    )

    grant = subparsers.add_parser("consent-grant", help="本人が対話端末で事前同意する")
    grant.add_argument("--hours", type=float, default=24)
    grant.add_argument(
        "--actions",
        nargs="+",
        choices=sorted(CONSENT_ACTIONS),
        default=sorted(CONSENT_ACTIONS),
    )
    subparsers.add_parser("consent-revoke", help="ローカル同意を失効させる")
    subparsers.add_parser("consent-status", help="全操作の同意状態を確認する")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "consent-grant":
            _grant_consent(_consent_path(args.consent_path), args.actions, args.hours)
            return 0
        if args.command == "consent-revoke":
            _write_receipt(_consent_path(args.consent_path), {"revoked": True})
            return 0
        if args.command == "consent-status":
            for action in sorted(CONSENT_ACTIONS):
                _require_consent(action, args.consent_path)
            print("全操作の同意が有効です")
            return 0
        _require_consent(args.command.replace("-", "_"), args.consent_path)
        if args.command == "put-text":
            text = Path(args.file).read_text(encoding="utf-8")
            put_text(text, consent_path=args.consent_path)
        elif args.command == "put-image":
            put_image(args.file, consent_path=args.consent_path)
        elif args.command == "get-text":
            sys.stdout.write(get_text(consent_path=args.consent_path))
        elif args.command == "restore":
            text = Path(args.file).read_text(encoding="utf-8")
            restore(text, consent_path=args.consent_path)
        else:  # pragma: no cover - argparse enforces choices
            parser.error(f"unknown command: {args.command}")
            return 2
    except OSError:
        print(
            "clipboard_bridge error: ローカルファイル操作に失敗しました",
            file=sys.stderr,
        )
        return 1
    except ClipboardBridgeError as exc:
        print(f"clipboard_bridge error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
