from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_gate(tmp_path: Path, observation: dict) -> tuple[int, dict]:
    path = tmp_path / "figure-observation.json"
    path.write_text(json.dumps(observation, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/note_figure_structure_gate.py"),
            str(path),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        check=False,
    )
    return result.returncode, json.loads(result.stdout)


def valid_observation() -> dict:
    return {
        "article_lane": "production_candidate",
        "figures": [
            {
                "id": "figure-dimension",
                "caption": "図：次元の罠のイメージ",
                "caption_tag": "figcaption",
                "previous_block": {"id": "concept-dimension", "tag": "p", "text_empty": False},
                "next_block": {"id": "detail-dimension", "tag": "p", "text_empty": False},
            }
        ],
        "concept_contracts": [
            {
                "concept": "次元の罠",
                "first_mention_block_id": "concept-dimension",
                "figure_id": "figure-dimension",
                "detail_block_id": "detail-dimension",
                "block_order": ["concept-dimension", "figure-dimension", "detail-dimension"],
            }
        ],
    }


def test_valid_concept_figure_detail_order_passes(tmp_path):
    returncode, payload = run_gate(tmp_path, valid_observation())
    assert returncode == 0
    assert payload["ready_for_draft_save"] is True
    assert payload["issues"] == []


def test_empty_caption_and_wrong_caption_tag_fail(tmp_path):
    observation = valid_observation()
    observation["figures"][0]["caption"] = ""
    observation["figures"][0]["caption_tag"] = "p"
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert {item["code"] for item in payload["issues"]} >= {
        "figure_caption_missing",
        "figure_caption_tag_invalid",
    }


def test_empty_paragraph_before_figure_fails(tmp_path):
    observation = valid_observation()
    observation["figures"][0]["previous_block"] = {
        "id": "empty-before",
        "tag": "p",
        "text_empty": True,
    }
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert "empty_paragraph_before_figure" in {
        item["code"] for item in payload["issues"]
    }


def test_concept_figure_detail_order_mismatch_fails(tmp_path):
    observation = valid_observation()
    observation["concept_contracts"][0]["block_order"] = [
        "figure-dimension",
        "concept-dimension",
        "detail-dimension",
    ]
    returncode, payload = run_gate(tmp_path, observation)
    assert returncode == 1
    assert "concept_figure_detail_order_invalid" in {
        item["code"] for item in payload["issues"]
    }
