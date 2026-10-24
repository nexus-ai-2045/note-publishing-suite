#!/usr/bin/env python3
"""Clipboard bridge for the note-publishing-suite operation department.

Standard input path for note editor text/image entry: put content onto the
macOS clipboard via `pbcopy` / `osascript`, then let a human or a browser
paste action deliver it into the editor (ProseMirror). This module never
opens a native file picker and never drives Computer Use; it only talks to
the OS clipboard via subprocess.

Design reference: docs/design/2026-09-11-three-departments.md (操作部門).

Functions:
    put_text(text) -> None
        Place text on the clipboard via `pbcopy`.
    put_image(path) -> None
        Place a PNG image on the clipboard via `osascript`
        (`set the clipboard to (read (POSIX file "...") as <<class PNGf>>)`).
    get_text() -> str
        Read current clipboard text via `pbpaste`.
    snapshot() -> str
        Alias for get_text(), named for the save/restore workflow.
    restore(previous_text) -> None
        Put a previously captured text snapshot back onto the clipboard.

All functions raise ClipboardBridgeError on subprocess failure.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


class ClipboardBridgeError(RuntimeError):
    """Raised when a clipboard subprocess call fails."""


def put_text(text: str) -> None:
    """Place `text` on the clipboard using `pbcopy`."""
    try:
        subprocess.run(
            ["pbcopy"],
            input=text,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        raise ClipboardBridgeError(f"pbcopy failed: {exc}") from exc


def put_image(path: str | Path) -> None:
    """Place the PNG image at `path` on the clipboard using `osascript`.

    Does not open any file picker or dialog. Uses AppleScript's
    `read ... as <<class PNGf>>` to load bytes and set the clipboard.
    """
    image_path = Path(path)
    if not image_path.exists():
        raise ClipboardBridgeError(f"image path does not exist: {image_path}")

    posix_path = str(image_path.resolve())
    escaped_path = posix_path.replace("\\", "\\\\").replace('"', '\\"')
    script = (
        f'set the clipboard to (read (POSIX file "{escaped_path}") '
        f"as «class PNGf»)"
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        raise ClipboardBridgeError(f"osascript put_image failed: {exc}") from exc


def get_text() -> str:
    """Return the current clipboard text via `pbpaste`."""
    try:
        result = subprocess.run(
            ["pbpaste"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        raise ClipboardBridgeError(f"pbpaste failed: {exc}") from exc
    return result.stdout


def snapshot() -> str:
    """Capture current clipboard text so it can be restored later."""
    return get_text()


def restore(previous_text: str) -> None:
    """Put a previously captured clipboard text snapshot back."""
    put_text(previous_text)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clipboard_bridge.py",
        description=(
            "Clipboard bridge CLI for note editor text/image entry. "
            "Never opens a file picker; OS clipboard only."
        ),
    )
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "put-text":
            text = Path(args.file).read_text(encoding="utf-8")
            put_text(text)
        elif args.command == "put-image":
            put_image(args.file)
        elif args.command == "get-text":
            sys.stdout.write(get_text())
        elif args.command == "restore":
            text = Path(args.file).read_text(encoding="utf-8")
            restore(text)
        else:  # pragma: no cover - argparse enforces choices
            parser.error(f"unknown command: {args.command}")
            return 2
    except ClipboardBridgeError as exc:
        print(f"clipboard_bridge error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
