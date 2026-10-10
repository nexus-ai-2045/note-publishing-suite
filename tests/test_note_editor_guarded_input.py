"""既存pytest入口から、任意Node環境の実入口試験と接続契約を確認する。"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_guarded_tab_backend():
    node = shutil.which("node")
    if not node:
        pytest.skip("単一URL入力の隔離試験にはNode.js 22以降が必要")
    result = subprocess.run(
        [node, "--test", "tests/note_editor_guarded_input.test.mjs"],
        cwd=ROOT, capture_output=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_editor_entrypoints_route_to_the_guard():
    module = "note_editor_guarded_input.mjs"
    for path in (
        "SKILL.md", "package.yaml", "skills/note-editor-prepublish/SKILL.md",
        "skills/note-editor-ops/SKILL.md", "references/note-editor-pdca-orchestration.md",
    ):
        assert module in (ROOT / path).read_text(encoding="utf-8"), path
    ops = (ROOT / "skills/note-editor-ops/SKILL.md").read_text(encoding="utf-8")
    assert "await input.pasteUrl({ checkpoint, payload: approvedSingleUrl })" in ops
    assert "await input.reconcile()" in ops
