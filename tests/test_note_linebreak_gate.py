from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_gate(tmp_path: Path, observation: dict) -> tuple[int, dict]:
    path = tmp_path / "linebreak-observation.json"
    path.write_text(json.dumps(observation, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/note_linebreak_gate.py"), str(path), "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        check=False,
    )
    return result.returncode, json.loads(result.stdout)


def valid_observation() -> dict:
    return {
        "article_lane": "production_candidate",
        "trailing_plain_br_count": 0,
        "consecutive_empty_paragraph_count": 0,
        "literal_backslash_linebreak_count": 0,
        "empty_paragraph_count": 2,
        "empty_paragraph_before_figure_count": 0,
        "paragraphs_with_multiple_plain_br_count": 20,
    }


def test_clean_structure_passes_with_review_warnings(tmp_path):
    returncode, payload = run_gate(tmp_path, valid_observation())
    assert returncode == 0
    assert payload["ready_for_draft_save"] is True
    assert {item["code"] for item in payload["warnings"]} == {
        "empty_paragraphs_review",
        "multiple_linebreaks_review",
    }


def test_trailing_plain_br_fails(tmp_path):
    observation = valid_observation()
    observation["trailing_plain_br_count"] = 1
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert "trailing_plain_br" in {item["code"] for item in payload["issues"]}


def test_consecutive_empty_and_literal_backslash_fail(tmp_path):
    observation = valid_observation()
    observation["consecutive_empty_paragraph_count"] = 1
    observation["literal_backslash_linebreak_count"] = 1
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert {item["code"] for item in payload["issues"]} >= {
        "consecutive_empty_paragraphs",
        "literal_backslash_linebreak",
    }


def test_empty_paragraph_before_figure_fails(tmp_path):
    observation = valid_observation()
    observation["empty_paragraph_before_figure_count"] = 1
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert "empty_paragraph_before_figure" in {
        item["code"] for item in payload["issues"]
    }


def test_missing_figure_linebreak_measurement_fails(tmp_path):
    observation = valid_observation()
    observation.pop("empty_paragraph_before_figure_count")
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert "empty_paragraph_before_figure_count_missing" in {
        item["code"] for item in payload["issues"]
    }
