#!/usr/bin/env python3
"""Note cover image upload measurement checker tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/note_cover_image_upload_check.py"


def run_checker(tmp_path: Path, payload: dict) -> tuple[int, dict]:
    path = tmp_path / "cover-measurement.json"
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
        "schema": "note_cover_image_upload_measurement.v1",
        "note_id": "n-fixture",
        "source_scope": "non-public editor_fixture draft",
        "image_source": {
            "path": "content/assets/automata/first-article/title-cover.jpg",
            "width": 1280,
            "height": 720,
            "bytes": 263237,
        },
        "publication_actions_performed": [],
        "public_actions_performed": [],
        "external_actions_performed": [
            "uploaded local cover image to non-public Note fixture draft via ChromeCodex"
        ],
        "routes": [
            {
                "surface": "in-app Browser",
                "status": "blocked",
                "observations": {
                    "file_input_generated_after_upload_click": True,
                    "automation_file_set_available": False,
                },
                "stop_causes": [
                    "in_app_browser_file_input_generated_but_no_supported_file_set_route"
                ],
            },
            {
                "surface": "ChromeCodex / Chrome extension API",
                "status": "passed",
                "observations": {
                    "existing_chrome_tabs_listed_before_claim": True,
                    "filechooser_event_observed": True,
                    "set_files_succeeded": True,
                    "crop_modal_observed": True,
                    "crop_save_clicked": True,
                    "image_visible_after_delay": True,
                    "draft_saved_notice_observed": True,
                },
                "uploaded_image": {
                    "alt": "eyecatch",
                    "natural_width": 1280,
                    "natural_height": 670,
                },
            },
        ],
    }


def valid_production_payload() -> dict:
    return {
        "schema": "note_cover_image_upload_production_record.v1",
        "note_id": "n-production",
        "source_scope": "non-public production candidate Note editor draft",
        "edit_url": "https://editor.note.com/notes/n-production/edit/",
        "article_title": "本番候補の下書き",
        "local_source": "content/drafts/example.md",
        "image_source": {
            "path": "content/assets/automata/first-article/title-cover.jpg",
            "width": 1280,
            "height": 720,
            "bytes": 263237,
        },
        "publication_actions_performed": [],
        "public_actions_performed": [],
        "external_actions_performed": [
            "uploaded local cover image to non-public Note production candidate draft via ChromeCodex"
        ],
        "surface": "ChromeCodex / Chrome extension API",
        "route": "chrome_extension_visible_editor_upload",
        "status": "passed",
        "observations": {
            "existing_chrome_tabs_listed_before_operation": True,
            "target_editor_url_confirmed": True,
            "target_title_confirmed": True,
            "pre_upload_publish_proceed_visible": True,
            "pre_upload_post_button_visible": False,
            "filechooser_event_observed": True,
            "set_files_succeeded": True,
            "crop_modal_observed": True,
            "crop_save_clicked": True,
            "image_visible_after_delay": True,
            "draft_save_clicked": True,
            "draft_saved_notice_observed": True,
            "post_save_publish_proceed_visible": True,
            "post_save_post_button_visible": False,
        },
        "uploaded_image": {
            "alt": "eyecatch",
            "natural_width": 1280,
            "natural_height": 670,
        },
        "draft_mutations_performed": [
            "uploaded cover image to non-public production candidate draft",
            "clicked crop modal save",
            "clicked draft save",
        ],
        "stop_causes": [],
    }


def codes(payload: dict) -> set[str]:
    return {item["code"] for item in payload["issues"]}


def test_valid_cover_upload_measurement_passes(tmp_path):
    returncode, payload = run_checker(tmp_path, valid_payload())

    assert returncode == 0
    assert payload["ok"] is True
    assert payload["routes"] == {
        "in_app_browser": "blocked",
        "chrome_codex": "passed",
    }
    assert payload["publication_actions_performed"] == []
    assert payload["public_actions_performed"] == []


def test_publication_action_fails(tmp_path):
    measurement = valid_payload()
    measurement["publication_actions_performed"] = ["clicked 投稿する"]

    returncode, payload = run_checker(tmp_path, measurement)

    assert returncode == 1
    assert "publication_action_recorded" in codes(payload)


def test_chrome_route_requires_success_signals(tmp_path):
    measurement = valid_payload()
    measurement["routes"][1]["observations"]["set_files_succeeded"] = False

    returncode, payload = run_checker(tmp_path, measurement)

    assert returncode == 1
    assert "chrome_success_signal_missing" in codes(payload)


def test_uploaded_cover_dimensions_are_checked(tmp_path):
    measurement = valid_payload()
    measurement["routes"][1]["uploaded_image"]["natural_height"] = 720

    returncode, payload = run_checker(tmp_path, measurement)

    assert returncode == 1
    assert "uploaded_dimensions_unexpected" in codes(payload)


def test_production_candidate_cover_upload_record_passes(tmp_path):
    returncode, payload = run_checker(tmp_path, valid_production_payload())

    assert returncode == 0
    assert payload["ok"] is True
    assert payload["routes"] == {
        "in_app_browser": "missing",
        "chrome_codex": "passed",
    }
    assert (
        payload["guarantee_scope"]
        == "cover_image_production_candidate_draft_save_only_no_publish_or_public_share"
    )


def test_production_candidate_rejects_publication_action(tmp_path):
    measurement = valid_production_payload()
    measurement["public_actions_performed"] = ["clicked 予約投稿"]

    returncode, payload = run_checker(tmp_path, measurement)

    assert returncode == 1
    assert "publication_action_recorded" in codes(payload)


def test_production_candidate_requires_draft_saved_notice(tmp_path):
    measurement = valid_production_payload()
    measurement["observations"]["draft_saved_notice_observed"] = False

    returncode, payload = run_checker(tmp_path, measurement)

    assert returncode == 1
    assert "chrome_success_signal_missing" in codes(payload)


def test_production_candidate_rejects_visible_post_button(tmp_path):
    measurement = valid_production_payload()
    measurement["observations"]["post_save_post_button_visible"] = True

    returncode, payload = run_checker(tmp_path, measurement)

    assert returncode == 1
    assert "public_button_state_unsafe" in codes(payload)
