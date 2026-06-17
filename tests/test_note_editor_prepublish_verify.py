#!/usr/bin/env python3
"""Note editor pre-publication observation checker tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_checker(tmp_path: Path, observation: dict) -> tuple[int, dict]:
    observation_path = tmp_path / "observation.json"
    observation_path.write_text(
        json.dumps(observation, ensure_ascii=False),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/note_editor_prepublish_verify.py"),
            str(observation_path),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    payload = json.loads(result.stdout)
    return result.returncode, payload


def ready_observation() -> dict:
    return {
        "title": "AUTOMATA No.5",
        "top_image": {"present": True},
        "toc_count": 1,
        "footer": {
            "required_urls": [
                "https://automata-lab.example/",
                "https://example.com/archive",
            ],
            "figures": [
                "https://automata-lab.example/",
                "https://example.com/archive",
            ],
            "raw_counts": {
                "https://automata-lab.example/": 0,
                "https://example.com/archive": 0,
            },
        },
        "magazine": {"target": "AUTOMATA", "added": True},
        "tags": ["AUTOMATA", "人工生命", "観測記録"],
        "article_type": "無料",
        "final_buttons": [{"label": "投稿する", "clicked": False}],
    }


def issue_codes(payload: dict) -> set[str]:
    return {issue["code"] for issue in payload["issues"]}


def test_ready_observation_passes(tmp_path):
    returncode, payload = run_checker(tmp_path, ready_observation())

    assert returncode == 0
    assert payload["ok"] is True
    assert payload["ready_for_publish"] is True
    assert payload["issues"] == []
    assert payload["manual_boundaries"] == []
    assert payload["publication_actions_performed"] == []


def test_manual_top_image_and_footer_boundaries_pass_but_block_ready(tmp_path):
    observation = ready_observation()
    observation["top_image"] = {"present": False}
    observation["footer"]["figures"] = []
    observation["footer"]["raw_counts"] = {
        "https://automata-lab.example/": 1,
        "https://example.com/archive": 1,
    }
    observation["manual_boundaries"] = {
        "top_image": "Codex in-app Browser returned File uploads are not supported",
        "footer_embeds": "Existing URL conversion mispositioned; kept raw URLs",
    }

    returncode, payload = run_checker(tmp_path, observation)

    assert returncode == 0
    assert payload["ok"] is True
    assert payload["ready_for_publish"] is False
    assert {item["code"] for item in payload["manual_boundaries"]} == {
        "top_image_manual_boundary",
        "footer_embed_manual_boundary",
    }


def test_duplicate_tags_fail(tmp_path):
    observation = ready_observation()
    observation["tags"] = ["#AUTOMATA", "automata", "観測記録"]

    returncode, payload = run_checker(tmp_path, observation)

    assert returncode == 1
    assert payload["ok"] is False
    assert "duplicate_tags" in issue_codes(payload)


def test_final_button_click_fails(tmp_path):
    observation = ready_observation()
    observation["final_buttons"] = [{"label": "投稿する", "clicked": True}]

    returncode, payload = run_checker(tmp_path, observation)

    assert returncode == 1
    assert payload["ok"] is False
    assert "final_button_clicked" in issue_codes(payload)


def test_raw_footer_url_without_boundary_fails(tmp_path):
    observation = ready_observation()
    observation["footer"]["figures"] = ["https://example.com/archive"]
    observation["footer"]["raw_counts"]["https://automata-lab.example/"] = 1

    returncode, payload = run_checker(tmp_path, observation)

    assert returncode == 1
    assert payload["ok"] is False
    assert "footer_raw_url" in issue_codes(payload)


def test_missing_required_publish_settings_fail(tmp_path):
    observation = ready_observation()
    observation["magazine"] = {"target": "AUTOMATA", "added": False}
    observation["article_type"] = ""
    observation["toc_count"] = 0

    returncode, payload = run_checker(tmp_path, observation)

    assert returncode == 1
    assert payload["ok"] is False
    assert {
        "magazine_missing",
        "article_type_missing",
        "toc_missing",
    }.issubset(issue_codes(payload))
