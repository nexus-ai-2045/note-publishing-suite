"""同意ゲートの検証。実クリップボードは触らない。"""

import json
import os
import stat
from types import SimpleNamespace
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
    path = tmp_path.resolve() / "consent.json"
    if os.name != "posix":
        # ロジック単体テストのI/O代替。実ストレージ拒否は独立テストで検証する。
        monkeypatch.setattr(
            cb, "_read_receipt", lambda p: json.loads(p.read_text(encoding="utf-8"))
        )
        monkeypatch.setattr(
            cb,
            "_write_receipt",
            lambda p, data: p.write_text(json.dumps(data), encoding="utf-8"),
        )
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
    path.chmod(0o600)
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


@pytest.mark.parametrize(
    "directory,mode,owner,links",
    [
        (True, stat.S_IFDIR | 0o755, 1000, 1),
        (True, stat.S_IFDIR | 0o700, 1001, 1),
        (False, stat.S_IFREG | 0o644, 1000, 1),
        (False, stat.S_IFREG | 0o600, 1001, 1),
        (False, stat.S_IFIFO | 0o600, 1000, 1),
        (False, stat.S_IFLNK | 0o600, 1000, 1),
        (False, stat.S_IFREG | 0o600, 1000, 2),
    ],
)
def test_storage_metadata_rejected(monkeypatch, directory, mode, owner, links):
    monkeypatch.setattr(cb.os, "getuid", lambda: 1000, raising=False)
    with pytest.raises(cb.ClipboardBridgeError):
        cb._validate_storage_stat(
            SimpleNamespace(st_mode=mode, st_uid=owner, st_nlink=links),
            directory=directory,
        )


def test_non_posix_storage_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / "receipt.json"
    monkeypatch.setattr(cb.os, "name", "nt")
    with pytest.raises(cb.ClipboardBridgeError):
        cb._write_receipt(path, {"revoked": True})
    assert not path.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions and dir_fd required")
@pytest.mark.parametrize(
    "attack",
    ["directory_mode", "file_mode", "symlink", "hardlink", "fifo", "ancestor_symlink"],
)
def test_unsafe_storage_rejected_without_clipboard(tmp_path, attack):
    root = tmp_path.resolve()
    parent = root / "private"
    parent.mkdir(mode=0o700)
    path = parent / "receipt.json"
    cb._write_receipt(path, {"revoked": True})
    original = path.read_bytes()
    if attack == "directory_mode":
        parent.chmod(0o777)
    elif attack == "file_mode":
        path.chmod(0o666)
    elif attack == "hardlink":
        os.link(path, parent / "second")
    elif attack == "ancestor_symlink":
        (root / "alias").symlink_to(parent, target_is_directory=True)
        path = root / "alias" / path.name
    else:
        path.unlink()
        if attack == "symlink":
            target = parent / "target"
            target.write_bytes(original)
            path.symlink_to(target)
        else:
            os.mkfifo(path, mode=0o600)
    with mock.patch.object(cb.subprocess, "run") as run:
        for operation in (
            lambda: cb.get_text(consent_path=path),
            lambda: cb._write_receipt(path, {"revoked": False}),
        ):
            with pytest.raises((cb.ClipboardBridgeError, OSError)):
                operation()
    run.assert_not_called()
    if attack in {
        "directory_mode",
        "file_mode",
        "hardlink",
        "ancestor_symlink",
        "symlink",
    }:
        assert path.read_bytes() == original


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions and dir_fd required")
def test_new_storage_private_under_permissive_umask(tmp_path):
    path = tmp_path.resolve() / "new" / "receipt.json"
    previous = os.umask(0)
    try:
        cb._write_receipt(path, {"revoked": True})
    finally:
        os.umask(previous)
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert cb._read_receipt(path) == {"revoked": True}


@pytest.mark.parametrize(
    "tags,error",
    [
        ([], None),
        ([2], None),
        ([2, 2], None),
        ([1], "denied"),
        ([2, 1], "denied"),
        ([0], "denied"),
        ([], "load"),
        ([], "null"),
        ([], "invalid"),
        ([], "entry"),
        ([2], "tag"),
    ],
)
def test_darwin_acl_inspection(monkeypatch, tags, error):
    monkeypatch.setattr(cb.platform, "system", lambda: "Darwin")
    library = mock.MagicMock()
    library.acl_get_fd_np.return_value = None if error == "null" else 123
    library.acl_valid.return_value = -1 if error == "invalid" else 0
    position = iter(tags)
    current = [None]

    def get_entry(acl, entry_id, output):
        if error == "entry":
            cb.ctypes.set_errno(cb.errno.EIO)
            return -1
        try:
            current[0] = next(position)
            output._obj.value = 456
            return 0
        except StopIteration:
            cb.ctypes.set_errno(cb.errno.EINVAL)
            return -1

    def get_tag(entry, output):
        output._obj.value = current[0]
        return -1 if error == "tag" else 0

    library.acl_get_entry.side_effect = get_entry
    library.acl_get_tag_type.side_effect = get_tag
    loader = mock.Mock(
        return_value=library, side_effect=OSError() if error == "load" else None
    )
    monkeypatch.setattr(cb.ctypes, "CDLL", loader)
    if error:
        with pytest.raises(cb.ClipboardBridgeError):
            cb._validate_darwin_acl(17)
    else:
        cb._validate_darwin_acl(17)
    if error != "load":
        library.acl_get_fd_np.assert_called_once_with(17, 0x100)
        if error != "null":
            library.acl_free.assert_called_once_with(123)


@pytest.mark.skipif(sys.platform != "darwin", reason="Darwin ACL API required")
@pytest.mark.parametrize("directory", [False, True])
def test_darwin_real_allow_acl_rejected(tmp_path, directory):
    # 自分が所有するテスト専用の一時ファイルだけにACLを設定する。
    path = tmp_path.resolve() / "acl-test"
    if directory:
        path.mkdir(mode=0o700)
    else:
        path.write_text("unchanged")
        path.chmod(0o600)
    subprocess.run(["/bin/chmod", "+a", "everyone allow write", str(path)], check=True)
    fd = os.open(path, os.O_RDONLY)
    try:
        with pytest.raises(cb.ClipboardBridgeError):
            cb._validate_storage_fd(fd, directory=directory)
    finally:
        os.close(fd)
