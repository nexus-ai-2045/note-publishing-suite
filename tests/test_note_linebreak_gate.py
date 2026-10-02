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


def test_expected_source_structure_accepts_intended_soft_breaks(tmp_path):
    observation = valid_observation()
    observation.update(expected_paragraph_soft_break_counts=[2, 0, 1], paragraph_soft_break_counts=[2, 0, 1])
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 0
    assert payload["ready_for_draft_save"] is True


def test_sentence_paragraph_regression_fails_source_comparison(tmp_path):
    observation = valid_observation()
    observation.update(expected_paragraph_soft_break_counts=[2, 0, 1], paragraph_soft_break_counts=[0, 0, 0, 0, 0, 0])
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert "source_paragraph_structure_mismatch" in {item["code"] for item in payload["issues"]}


def test_same_total_soft_breaks_in_wrong_paragraphs_fail(tmp_path):
    observation = valid_observation()
    observation.update(expected_paragraph_soft_break_counts=[2, 0, 1], paragraph_soft_break_counts=[1, 0, 2])
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert "source_paragraph_structure_mismatch" in {item["code"] for item in payload["issues"]}


def test_expected_structure_requires_observation(tmp_path):
    observation = valid_observation()
    observation["expected_paragraph_soft_break_counts"] = [1]
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert "paragraph_soft_break_counts_invalid" in {item["code"] for item in payload["issues"]}


def test_invalid_expected_structure_fails(tmp_path):
    observation = valid_observation()
    observation.update(expected_paragraph_soft_break_counts=[True, -1], paragraph_soft_break_counts=[0, 0])
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert "expected_paragraph_soft_break_counts_invalid" in {item["code"] for item in payload["issues"]}


def test_observed_structure_requires_expectation(tmp_path):
    observation = valid_observation()
    observation["paragraph_soft_break_counts"] = [1]
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert "expected_paragraph_soft_break_counts_invalid" in {item["code"] for item in payload["issues"]}


def test_noninteger_observed_break_count_fails(tmp_path):
    observation = valid_observation()
    observation.update(expected_paragraph_soft_break_counts=[0], paragraph_soft_break_counts=[False])
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert "paragraph_soft_break_counts_invalid" in {item["code"] for item in payload["issues"]}
