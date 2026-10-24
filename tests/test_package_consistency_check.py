from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/package_consistency_check.py"


def run_check(*args: str) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode, json.loads(result.stdout)


def test_standalone_default_checks_declarations_without_guessing_skill_copy():
    returncode, payload = run_check()
    assert returncode == 0, payload
    assert payload["ok"] is True
    assert payload["copy_sync_checked"] is False
    assert payload["copy_sync_findings"] == []
    assert "skill_copy" not in payload


def test_explicit_missing_skill_copy_fails_closed(tmp_path: Path):
    missing = tmp_path / "missing-skill-copy"
    returncode, payload = run_check("--skill-copy", str(missing))
    assert returncode == 1
    assert payload["copy_sync_checked"] is True
    assert payload["skill_copy"] == missing.as_posix()
    assert payload["copy_sync_findings"] == [
        {"kind": "missing_skill_copy", "path": str(missing)}
    ]
