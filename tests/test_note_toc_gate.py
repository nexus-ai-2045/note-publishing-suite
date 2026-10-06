from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_gate(tmp_path: Path, observation: dict) -> tuple[int, dict]:
    path = tmp_path / "toc-observation.json"
    path.write_text(json.dumps(observation, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/note_toc_gate.py"), str(path), "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        check=False,
    )
    return result.returncode, json.loads(result.stdout)


def valid_observation() -> dict:
    return {
        "article_lane": "production_candidate",
        "h2_count": 16,
        "h3_count": 1,
        "toc_count": 1,
        "toc_ref_count": 17,
        "toc_before_first_heading": True,
        "toc_contenteditable": "false",
    }


def test_valid_live_toc_passes(tmp_path):
    returncode, payload = run_gate(tmp_path, valid_observation())
    assert returncode == 0
    assert payload["ready_for_draft_save"] is True


def test_missing_toc_fails(tmp_path):
    observation = valid_observation()
    observation["toc_count"] = 0
    observation["toc_ref_count"] = 0
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert {issue["code"] for issue in payload["issues"]} >= {
        "toc_missing",
        "toc_refs_incomplete",
    }


def test_toc_after_first_heading_fails(tmp_path):
    observation = valid_observation()
    observation["toc_before_first_heading"] = False
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert "toc_position_invalid" in {issue["code"] for issue in payload["issues"]}
