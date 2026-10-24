"""通常検査が別worktreeのテストを混ぜないことを実際のpytest収集で確認する。"""
from pathlib import Path
import subprocess
import sys


def test_default_collection_excludes_foreign_worktree(tmp_path):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "pytest.ini").write_bytes((root / "pytest.ini").read_bytes())
    for directory in ("tests", "scripts", ".worktrees/foreign/tests"):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / "tests/test_owned.py").write_text("def test_owned(): pass\n")
    (tmp_path / "scripts/test_skill_integration.py").write_text("def test_integration(): pass\n")
    (tmp_path / ".worktrees/foreign/tests/test_foreign.py").write_text(
        "raise AssertionError('foreign worktree must not be imported')\n")
    result = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "test_owned.py::test_owned" in result.stdout
    assert "test_skill_integration.py::test_integration" in result.stdout
    assert "foreign" not in result.stdout
