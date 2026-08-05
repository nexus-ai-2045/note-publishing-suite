#!/usr/bin/env python3
"""Note editor toolbar measurement checker tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/note_editor_toolbar_measurement_check.py"


def run_checker(tmp_path: Path, payload: dict) -> tuple[int, dict]:
    path = tmp_path / "measurement.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(CHECKER), str(path), "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode, json.loads(result.stdout)


def valid_payload() -> dict:
    return {
        "schema": "note_editor_toolbar_variant_measurement.v1",
        "note_id": "n-fixture",
        "source_scope": "non-public note editor fixture draft",
        "publication_actions_performed": [],
        "external_actions_performed": [],
        "variants": [
            {
                "label": "viewport_390x844_default_focus",
                "state": {
                    "viewport": {"width": 390, "height": 844},
                    "selection": {"text": "", "rangeCount": 1},
                    "buttons": [
                        {
                            "label": "メニューを開く",
                            "ariaLabel": "メニューを開く",
                            "nearBottom": True,
                            "nearLeft": True,
                            "role": "button",
                        },
                        {
                            "label": "下書き保存",
                            "ariaLabel": "",
                            "nearBottom": False,
                            "nearLeft": False,
                            "role": "button",
                        },
                    ],
                },
            },
            {
                "label": "viewport_1280x720_default_focus",
                "state": {
                    "viewport": {"width": 1280, "height": 720},
                    "selection": {"text": "", "rangeCount": 1},
                    "buttons": [
                        {
                            "label": "目次",
                            "ariaLabel": "目次",
                            "nearBottom": False,
                            "nearLeft": True,
                            "role": "button",
                        },
                        {
                            "label": "エディタのガイド",
                            "ariaLabel": "エディタのガイド",
                            "nearBottom": False,
                            "nearLeft": True,
                            "role": "button",
                        },
                    ],
                },
            },
        ],
        "stop_causes": [
            "selection_toolbar_not_measured_non_empty_selection_not_observed"
        ],
    }


def codes(payload: dict) -> set[str]:
    return {item["code"] for item in payload["issues"]}


def test_valid_measurement_passes_but_reports_incomplete_coverage(tmp_path):
    returncode, payload = run_checker(tmp_path, valid_payload())

    assert returncode == 0
    assert payload["ok"] is True
    assert payload["coverage_complete"] is False
    assert payload["observed_variants"] == ["footer_toolbar", "side_like_toolbar"]
    assert payload["unverified_variants"] == [
        "selection_toolbar_not_measured_non_empty_selection_not_observed"
    ]
    assert payload["publication_actions_performed"] == []
    assert payload["external_actions_performed"] == []


def test_publication_action_fails(tmp_path):
    measurement = valid_payload()
    measurement["publication_actions_performed"] = ["clicked 投稿する"]

    returncode, payload = run_checker(tmp_path, measurement)

    assert returncode == 1
    assert "publication_action_recorded" in codes(payload)


def test_missing_fixture_scope_fails(tmp_path):
    measurement = valid_payload()
    measurement["source_scope"] = "production article"

    returncode, payload = run_checker(tmp_path, measurement)

    assert returncode == 1
    assert "not_fixture_scope" in codes(payload)


def test_missing_toolbar_variants_fail(tmp_path):
    measurement = valid_payload()
    measurement["variants"] = [
        {
            "label": "viewport_390x844_default_focus",
            "state": {
                "viewport": {"width": 390, "height": 844},
                "buttons": [{"label": "下書き保存", "nearBottom": False}],
            },
        }
    ]

    returncode, payload = run_checker(tmp_path, measurement)

    assert returncode == 1
    assert "footer_toolbar_not_observed" in codes(payload)
    assert "side_like_toolbar_not_observed" in codes(payload)


def test_required_observed_variants_can_scope_chrome_measurement(tmp_path):
    measurement = valid_payload()
    measurement["required_observed_variants"] = [
        "side_like_toolbar",
        "selection_toolbar_signal",
    ]
    measurement["variants"][0]["state"]["buttons"] = [
        {"label": "下書き保存", "nearBottom": False}
    ]
    measurement["variants"][1]["state"]["selection"] = {
        "text": "SELECT_ME_FOR_TOOLBAR_CHECK",
        "rangeCount": 1,
    }
    measurement["stop_causes"] = [
        "footer_toolbar_not_measured_chrome_window_not_resized",
        "context_menu_not_measured_no_distinct_context_menu_dom_observed",
    ]

    returncode, payload = run_checker(tmp_path, measurement)

    assert returncode == 0
    assert payload["required_observed_variants"] == [
        "side_like_toolbar",
        "selection_toolbar_signal",
    ]
    assert payload["observed_variants"] == [
        "selection_toolbar_signal",
        "side_like_toolbar",
    ]
    assert "footer_toolbar_not_observed" not in codes(payload)


def test_right_click_with_normal_link_toolbar_is_not_context_menu(tmp_path):
    measurement = valid_payload()
    measurement["variants"].append(
        {
            "label": "viewport_1280x720_marker_right_click",
            "state": {
                "viewport": {"width": 1280, "height": 720},
                "selection": {"text": "", "rangeCount": 0},
                "buttons": [
                    {
                        "label": "リンク",
                        "ariaLabel": "リンク",
                        "nearBottom": True,
                        "nearLeft": True,
                        "role": "button",
                    }
                ],
            },
        }
    )
    measurement["stop_causes"].append(
        "context_menu_not_measured_no_distinct_context_menu_dom_observed"
    )

    returncode, payload = run_checker(tmp_path, measurement)

    assert returncode == 0
    assert payload["observed_variants"] == ["footer_toolbar", "side_like_toolbar"]
    assert "context_menu_signal" not in payload["observed_variants"]
    assert (
        "context_menu_not_measured_no_distinct_context_menu_dom_observed"
        in payload["unverified_variants"]
    )
