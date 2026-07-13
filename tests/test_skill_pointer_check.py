from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/skill_pointer_check.py"


def run_checker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), *args, "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_package_pointer_targets_exist() -> None:
    result = run_checker()
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["checked_targets"]


def test_installed_pointer_target_disappearance_fails_closed(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    env = os.environ.copy()
    env["CLAUDE_SKILLS_DIR"] = str(skills_root)
    install = subprocess.run(
        ["bash", "adapters/claude-code/install.sh", str(tmp_path / "workspace")],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr

    pointer = skills_root / "note-publishing-suite" / "SKILL.md"
    pointer.write_text(
        pointer.read_text(encoding="utf-8").replace(
            f"{ROOT}/SKILL.md", f"{ROOT}/missing-ssot/SKILL.md"
        ),
        encoding="utf-8",
    )

    result = run_checker("--installed-root", str(skills_root))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any("missing installed SSOT target" in error for error in payload["errors"])
