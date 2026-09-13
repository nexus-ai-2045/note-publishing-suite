"""同意ゲートの検証。実クリップボードは触らない。"""

import json
import plistlib
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import clipboard_bridge as cb


@pytest.fixture
def receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(cb, "_device_id", lambda: "test-device-1")
    path = tmp_path / "consent.json"
    now = time.time()
    data = dict(
        version=1,
        principal=cb._principal(),
        issued_at=now - 1,
        expires_at=now + 3600,
        revoked=False,
        confirmation="interactive-typed",
        actions=sorted(cb.CONSENT_ACTIONS),
    )
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(
        cb, "_consent_path", lambda value=None: Path(value) if value else path
    )
    return path


@pytest.mark.parametrize("action", sorted(cb.CONSENT_ACTIONS))
@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "malformed",
        "expired",
        "future",
        "wrong_user",
        "wrong_machine",
        "revoked",
        "denied",
        "too_long",
        "nan",
        "bad_actions",
    ],
)
def test_denied_before_subprocess(receipt, action, failure):
    data = json.loads(receipt.read_text())
    if failure == "missing":
        receipt.unlink()
    elif failure == "malformed":
        receipt.write_text("[]")
    else:
        if failure == "expired":
            data["expires_at"] = time.time() - 10
        if failure == "future":
            data["issued_at"] = time.time() + 10
        if failure == "wrong_user":
            data["principal"]["user"] = "other"
        if failure == "wrong_machine":
            data["principal"]["machine"] = "other"
        if failure == "revoked":
            data["revoked"] = True
        if failure == "denied":
            data["actions"] = []
        if failure == "too_long":
            data["expires_at"] = time.time() + 100000
        if failure == "nan":
            data["issued_at"] = float("nan")
        if failure == "bad_actions":
            data["actions"] = [1]
        receipt.write_text(json.dumps(data))
    args = ("content",) if action in {"put_text", "put_image", "restore"} else ()
    with mock.patch.object(cb.subprocess, "run") as run:
        with pytest.raises(cb.ClipboardBridgeError):
            getattr(cb, action)(*args)
    run.assert_not_called()


@pytest.mark.parametrize(
    "action,command",
    [
        ("put_text", "pbcopy"),
        ("restore", "pbcopy"),
        ("get_text", "pbpaste"),
        ("snapshot", "pbpaste"),
        ("put_image", "osascript"),
    ],
)
def test_allowed_operation(receipt, tmp_path, action, command):
    image = tmp_path / "cover.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    args = (
        (image,)
        if action == "put_image"
        else ("hello",) if action in {"put_text", "restore"} else ()
    )
    with mock.patch.object(
        cb.subprocess,
        "run",
        return_value=subprocess.CompletedProcess([], 0, stdout="hello"),
    ) as run:
        value = getattr(cb, action)(*args)
    assert run.call_args.args[0][0] == command
    if action in {"snapshot", "get_text"}:
        assert value == "hello"
    if action in {"restore", "put_text"}:
        assert run.call_args.kwargs["input"] == "hello"
    if action == "put_image":
        assert "choose file" not in run.call_args.args[0][2]


@pytest.mark.parametrize("answer", ["", "yes", "no", cb.CONSENT_PHRASE])
def test_interactive_grant(receipt, answer):
    receipt.unlink()
    with mock.patch.object(
        cb.sys.stdin, "isatty", return_value=True
    ), mock.patch.object(cb.sys.stdout, "isatty", return_value=True), mock.patch(
        "builtins.input", return_value=answer
    ), mock.patch.object(
        cb.subprocess, "run"
    ) as run:
        assert cb.main(["consent-grant", "--hours", "1", "--actions", "put_text"]) == (
            0 if answer == cb.CONSENT_PHRASE else 1
        )
    assert receipt.exists() == (answer == cb.CONSENT_PHRASE)
    run.assert_not_called()
    if receipt.exists():
        cb._require_consent("put_text")
        with pytest.raises(cb.ClipboardBridgeError):
            cb._require_consent("get_text")
        assert cb.main(["consent-revoke"]) == 0
        with pytest.raises(cb.ClipboardBridgeError):
            cb._require_consent("put_text")


def test_noninteractive_grant_denied(receipt):
    receipt.unlink()
    with mock.patch.object(cb.sys.stdin, "isatty", return_value=False):
        assert cb.main(["consent-grant"]) == 1
    assert not receipt.exists()


@pytest.mark.parametrize("hours", ["0", "25", "nan", "inf"])
def test_invalid_duration(receipt, hours):
    receipt.unlink()
    with mock.patch.object(
        cb.sys.stdin, "isatty", return_value=True
    ), mock.patch.object(cb.sys.stdout, "isatty", return_value=True):
        assert cb.main(["consent-grant", "--hours", hours]) == 1
    assert not receipt.exists()


@pytest.mark.parametrize("command", ["put-text", "put-image", "restore", "get-text"])
def test_cli_denied(receipt, command, capsys):
    receipt.unlink()
    args = [command] + (["--file", "missing"] if command != "get-text" else [])
    with mock.patch.object(cb.subprocess, "run") as run:
        assert cb.main(args) == 1
    run.assert_not_called()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("command", ["put-text", "restore", "put-image", "get-text"])
def test_cli_allowed(receipt, tmp_path, command):
    path = tmp_path / "input.txt"
    path.write_text("hello")
    args = ["--consent-path", str(receipt), command] + (
        ["--file", str(path)] if command != "get-text" else []
    )
    with mock.patch.object(
        cb.subprocess,
        "run",
        return_value=subprocess.CompletedProcess([], 0, stdout="hello"),
    ) as run:
        assert cb.main(args) == 0
    run.assert_called_once()


def test_no_error_content_leak(receipt, capsys):
    with mock.patch.object(
        cb.subprocess,
        "run",
        side_effect=subprocess.CalledProcessError(
            1, ["secret"], output="secret", stderr="secret"
        ),
    ):
        assert cb.main(["get-text"]) == 1
    out = capsys.readouterr()
    assert "secret" not in out.out + out.err


def test_explicit_missing_does_not_fallback(receipt, tmp_path):
    with mock.patch.object(cb.subprocess, "run") as run:
        with pytest.raises(cb.ClipboardBridgeError):
            cb.get_text(consent_path=tmp_path / "missing")
    run.assert_not_called()


def test_copied_receipt_same_user_and_hostname_denied(receipt, monkeypatch):
    # 同じ利用者名・UID・ホスト名でも、別端末のUUIDならコピーされた同意を拒否する。
    monkeypatch.setattr(cb.platform, "node", lambda: "identical-hostname")
    monkeypatch.setattr(cb, "_device_id", lambda: "test-device-2")
    with mock.patch.object(cb.subprocess, "run") as run:
        with pytest.raises(cb.ClipboardBridgeError):
            cb.get_text(consent_path=receipt)
    run.assert_not_called()


def test_unavailable_device_denied_before_clipboard(receipt, monkeypatch):
    def unavailable():
        raise cb.ClipboardBridgeError("対応する端末識別子を確認できません")

    monkeypatch.setattr(cb, "_device_id", unavailable)
    with mock.patch.object(cb.subprocess, "run") as run:
        with pytest.raises(cb.ClipboardBridgeError):
            cb.get_text(consent_path=receipt)
    run.assert_not_called()


def test_device_uuid_read_and_normalized(monkeypatch):
    monkeypatch.setattr(cb.platform, "system", lambda: "Darwin")
    payload = plistlib.dumps(
        [{"IOPlatformUUID": "12345678-1234-1234-ABCD-123456789ABC"}]
    )
    with mock.patch.object(
        cb.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, payload)
    ) as run:
        assert (
            cb._device_id()
            == "macos-ioplatformuuid:12345678-1234-1234-abcd-123456789abc"
        )
    assert run.call_args.args[0] == [
        "/usr/sbin/ioreg",
        "-a",
        "-r",
        "-d",
        "1",
        "-c",
        "IOPlatformExpertDevice",
    ]
    assert run.call_args.kwargs["timeout"] == 5


@pytest.mark.parametrize(
    "payload",
    [
        b"garbage",
        b"<?xml version='1.0'?><plist><broken>",
        plistlib.dumps([]),
        plistlib.dumps([{}]),
        plistlib.dumps([{"IOPlatformUUID": ""}]),
        plistlib.dumps([{"IOPlatformUUID": "00000000-0000-0000-0000-000000000000"}]),
        plistlib.dumps([{"IOPlatformUUID": "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF"}]),
        plistlib.dumps([{"IOPlatformUUID": 123}]),
        plistlib.dumps(
            [{"IOPlatformUUID": "12345678-1234-1234-abcd-123456789abc"}] * 2
        ),
    ],
)
def test_device_invalid_response_denied(monkeypatch, payload):
    monkeypatch.setattr(cb.platform, "system", lambda: "Darwin")
    with mock.patch.object(
        cb.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, payload)
    ):
        with pytest.raises(cb.ClipboardBridgeError):
            cb._device_id()


@pytest.mark.parametrize(
    "error",
    [
        OSError("private details"),
        subprocess.CalledProcessError(1, ["private details"]),
        subprocess.TimeoutExpired("private details", 5),
    ],
)
def test_device_command_failure_fixed_error(monkeypatch, error):
    monkeypatch.setattr(cb.platform, "system", lambda: "Darwin")
    with mock.patch.object(cb.subprocess, "run", side_effect=error):
        with pytest.raises(cb.ClipboardBridgeError) as raised:
            cb._device_id()
    assert "private" not in str(raised.value)


@pytest.mark.parametrize("system", ["Windows", "Linux", ""])
def test_unsupported_platform_no_fallback(monkeypatch, system):
    monkeypatch.setattr(cb.platform, "system", lambda: system)
    with mock.patch.object(cb.subprocess, "run") as run:
        with pytest.raises(cb.ClipboardBridgeError):
            cb._device_id()
    run.assert_not_called()
