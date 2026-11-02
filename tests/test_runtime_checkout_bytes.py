"""Git checkout conversion must preserve the bytes used for runtime adoption."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_crlf_checkout_preserves_adopted_source_bytes(tmp_path):
    global_config = tmp_path / "empty-git-config"
    global_config.write_bytes(b"")
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(global_config),
               GIT_AUTHOR_NAME="fixture", GIT_COMMITTER_NAME="fixture",
               GIT_AUTHOR_EMAIL="fixture@example.invalid",
               GIT_COMMITTER_EMAIL="fixture@example.invalid")
    source, target = tmp_path / "source", tmp_path / "checkout"
    source.mkdir()

    def git(*args, cwd=source):
        return subprocess.check_output(["git", *args], cwd=cwd, env=env, stderr=subprocess.PIPE)

    git("init", "-q")
    (source / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    (source / "scripts").mkdir()
    for name in ("probe.py", "probe.js", "probe.mjs", "probe.ps1"):
        (source / "scripts" / name).write_bytes(b"fixture\n")
    (source / "package.yaml").write_bytes(b"name: fixture\n")
    git("add", ".")
    git("commit", "-qm", "fixture")
    git("-c", "core.autocrlf=true", "clone", "-q", "--no-local", str(source), str(target))
    for name in (".gitattributes", "package.yaml", "scripts/probe.py", "scripts/probe.js", "scripts/probe.mjs"):
        assert (target / name).read_bytes() == git("show", "HEAD:" + name), name
    assert (target / "scripts/probe.ps1").read_bytes() == b"fixture\r\n"
