"""Tests for scripts/clipboard_bridge.py.

All subprocess calls are mocked; no real OS clipboard is touched.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import clipboard_bridge  # noqa: E402


def _completed(stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["mock"], returncode=0, stdout=stdout, stderr=""
    )


class TestPutText:
    def test_calls_pbcopy_with_text_input(self):
        with mock.patch.object(
            clipboard_bridge.subprocess, "run", return_value=_completed()
        ) as mock_run:
            clipboard_bridge.put_text("hello note")

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0] == ["pbcopy"]
        assert kwargs["input"] == "hello note"
        assert kwargs["text"] is True
        assert kwargs["check"] is True

    def test_raises_bridge_error_on_called_process_error(self):
        with mock.patch.object(
            clipboard_bridge.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, ["pbcopy"]),
        ):
            with pytest.raises(clipboard_bridge.ClipboardBridgeError):
                clipboard_bridge.put_text("hello")

    def test_raises_bridge_error_on_os_error(self):
        with mock.patch.object(
            clipboard_bridge.subprocess, "run", side_effect=OSError("no pbcopy")
        ):
            with pytest.raises(clipboard_bridge.ClipboardBridgeError):
                clipboard_bridge.put_text("hello")


class TestPutImage:
    def test_calls_osascript_with_clipboard_script(self, tmp_path):
        image_path = tmp_path / "cover.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        with mock.patch.object(
            clipboard_bridge.subprocess, "run", return_value=_completed()
        ) as mock_run:
            clipboard_bridge.put_image(image_path)

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        command = args[0]
        assert command[0] == "osascript"
        assert command[1] == "-e"
        script = command[2]
        assert "set the clipboard to" in script
        assert "PNGf" in script
        assert str(image_path.resolve()) in script
        assert kwargs["check"] is True

    def test_missing_file_raises_before_subprocess(self, tmp_path):
        missing = tmp_path / "does-not-exist.png"
        with mock.patch.object(clipboard_bridge.subprocess, "run") as mock_run:
            with pytest.raises(clipboard_bridge.ClipboardBridgeError):
                clipboard_bridge.put_image(missing)
        mock_run.assert_not_called()

    def test_raises_bridge_error_on_called_process_error(self, tmp_path):
        image_path = tmp_path / "cover.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        with mock.patch.object(
            clipboard_bridge.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, ["osascript"]),
        ):
            with pytest.raises(clipboard_bridge.ClipboardBridgeError):
                clipboard_bridge.put_image(image_path)

    def test_never_invokes_file_dialog_style_commands(self, tmp_path):
        # The put_image implementation must not shell out to any command
        # that could open a native file picker/dialog.
        image_path = tmp_path / "cover.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        with mock.patch.object(
            clipboard_bridge.subprocess, "run", return_value=_completed()
        ) as mock_run:
            clipboard_bridge.put_image(image_path)

        command = mock_run.call_args[0][0]
        joined = " ".join(command)
        for forbidden in ("open -a", "osascript -e activate", "choose file"):
            assert forbidden not in joined


class TestGetText:
    def test_calls_pbpaste_and_returns_stdout(self):
        with mock.patch.object(
            clipboard_bridge.subprocess,
            "run",
            return_value=_completed(stdout="clipboard content"),
        ) as mock_run:
            result = clipboard_bridge.get_text()

        assert result == "clipboard content"
        args, kwargs = mock_run.call_args
        assert args[0] == ["pbpaste"]
        assert kwargs["check"] is True

    def test_raises_bridge_error_on_failure(self):
        with mock.patch.object(
            clipboard_bridge.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, ["pbpaste"]),
        ):
            with pytest.raises(clipboard_bridge.ClipboardBridgeError):
                clipboard_bridge.get_text()


class TestSnapshotAndRestore:
    def test_snapshot_delegates_to_get_text(self):
        with mock.patch.object(
            clipboard_bridge, "get_text", return_value="previous value"
        ) as mock_get_text:
            result = clipboard_bridge.snapshot()

        assert result == "previous value"
        mock_get_text.assert_called_once_with()

    def test_restore_delegates_to_put_text(self):
        with mock.patch.object(clipboard_bridge, "put_text") as mock_put_text:
            clipboard_bridge.restore("saved value")

        mock_put_text.assert_called_once_with("saved value")

    def test_snapshot_then_restore_round_trip(self):
        with mock.patch.object(
            clipboard_bridge.subprocess, "run", return_value=_completed()
        ) as mock_run:
            mock_run.return_value = _completed(stdout="original clipboard")
            saved = clipboard_bridge.snapshot()

            mock_run.return_value = _completed()
            clipboard_bridge.restore(saved)

        # Last call should be the restore's pbcopy with the original text.
        args, kwargs = mock_run.call_args
        assert args[0] == ["pbcopy"]
        assert kwargs["input"] == "original clipboard"


class TestCli:
    def test_put_text_reads_file_and_calls_put_text(self, tmp_path):
        text_file = tmp_path / "body.txt"
        text_file.write_text("記事本文", encoding="utf-8")

        with mock.patch.object(clipboard_bridge, "put_text") as mock_put_text:
            exit_code = clipboard_bridge.main(["put-text", "--file", str(text_file)])

        assert exit_code == 0
        mock_put_text.assert_called_once_with("記事本文")

    def test_put_image_reads_file_arg_and_calls_put_image(self, tmp_path):
        image_file = tmp_path / "cover.png"
        image_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        with mock.patch.object(clipboard_bridge, "put_image") as mock_put_image:
            exit_code = clipboard_bridge.main(
                ["put-image", "--file", str(image_file)]
            )

        assert exit_code == 0
        mock_put_image.assert_called_once_with(str(image_file))

    def test_get_text_prints_clipboard_content(self, capsys):
        with mock.patch.object(
            clipboard_bridge, "get_text", return_value="clipboard value"
        ):
            exit_code = clipboard_bridge.main(["get-text"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out == "clipboard value"

    def test_restore_reads_snapshot_file_and_calls_restore(self, tmp_path):
        snapshot_file = tmp_path / "snapshot.txt"
        snapshot_file.write_text("saved snapshot", encoding="utf-8")

        with mock.patch.object(clipboard_bridge, "restore") as mock_restore:
            exit_code = clipboard_bridge.main(
                ["restore", "--file", str(snapshot_file)]
            )

        assert exit_code == 0
        mock_restore.assert_called_once_with("saved snapshot")

    def test_cli_reports_bridge_error_with_exit_code_1(self, tmp_path, capsys):
        text_file = tmp_path / "body.txt"
        text_file.write_text("text", encoding="utf-8")

        with mock.patch.object(
            clipboard_bridge,
            "put_text",
            side_effect=clipboard_bridge.ClipboardBridgeError("boom"),
        ):
            exit_code = clipboard_bridge.main(["put-text", "--file", str(text_file)])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "boom" in captured.err

    def test_cli_requires_a_subcommand(self):
        with pytest.raises(SystemExit):
            clipboard_bridge.main([])
