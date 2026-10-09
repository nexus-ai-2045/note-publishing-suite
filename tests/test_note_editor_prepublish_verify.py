#!/usr/bin/env python3
"""Note editor pre-publication observation checker tests."""

from __future__ import annotations

import json
import hashlib
import copy
import pytest
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


def selection_plan() -> dict:
    plan = {
        "article_id": "fixture-article",
        "reader": "関心を持つ読者",
        "series": "fixture-series",
        "reader_action": "関連資料を読む",
        "links": [
            {
                "url": url,
                "registry_ref": "fixture://registered-links",
                "reason": "読者の次の行動に合う",
                "presentation": "card",
                "required": True,
            }
            for url in ["https://automata-lab.example/", "https://example.com/archive"]
        ],
    }
    return reviewed(plan)


def reviewed(plan: dict) -> dict:
    plan.pop("review", None)
    digest = hashlib.sha256(
        json.dumps(
            plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    plan["review"] = {
        "status": "approved",
        "reviewer": "fixture-human",
        "reviewed_at": "2026-01-01T00:00:00+00:00",
        "plan_sha256": digest,
    }
    return plan


def ready_observation() -> dict:
    return {
        "title": "AUTOMATA No.5",
        "top_image": {"present": True},
        "toc_count": 1,
        "article_id": "fixture-article",
        "series": "fixture-series",
        "production_plan": selection_plan(),
        "footer": {
            "nodes": [
                {"tag": "FIGURE", "data_src": "https://automata-lab.example/"},
                {"tag": "FIGURE", "hrefs": ["https://example.com/archive"]},
            ]
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
    assert payload["ready_for_publish"] is False
    assert payload["live_dom_verified"] is False
    assert payload["verification_scope"] == "supplied_snapshot_only"
    assert payload["issues"] == []
    assert payload["manual_boundaries"] == []
    assert payload["publication_actions_performed"] == []


def test_manual_footer_boundary_is_not_pass(tmp_path):
    observation = ready_observation()
    observation["top_image"] = {"present": False}
    observation["footer"]["nodes"] = []
    observation["footer"]["raw_counts"] = {
        "https://automata-lab.example/": 1,
        "https://example.com/archive": 1,
    }
    observation["manual_boundaries"] = {
        "top_image": "Codex in-app Browser returned File uploads are not supported",
        "footer_embeds": "Existing URL conversion mispositioned; kept raw URLs",
    }

    returncode, payload = run_checker(tmp_path, observation)

    assert returncode == 1
    assert payload["ok"] is False
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
    observation["footer"]["nodes"][0] = {
        "tag": "A",
        "href": "https://automata-lab.example/",
        "text": "https://automata-lab.example/",
    }

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


@pytest.mark.parametrize(
    "fault",
    [
        "missing_plan",
        "empty_plan",
        "empty_links",
        "unreviewed",
        "stale_review",
        "wrong_article",
        "wrong_series",
        "missing",
        "extra",
        "order",
        "duplicate",
        "wrong_presentation",
        "unknown_node",
        "empty_nodes",
        "bad_review_time",
        "future_review_time",
        "missing_registry",
        "duplicate_plan_url",
        "bad_required",
        "bad_url",
        "ambiguous_figure",
    ],
)
def test_footer_contract_rejects_failure_paths(tmp_path, fault):
    obs = ready_observation()
    plan = obs["production_plan"]
    nodes = obs["footer"]["nodes"]
    if fault == "missing_plan":
        obs.pop("production_plan")
    elif fault == "empty_plan":
        obs["production_plan"] = {}
    elif fault == "empty_links":
        obs["production_plan"] = reviewed(plan | {"links": []})
    elif fault == "unreviewed":
        plan["review"]["status"] = "pending"
    elif fault == "stale_review":
        plan["reader_action"] = "changed"
    elif fault == "wrong_article":
        obs["article_id"] = "other"
    elif fault == "wrong_series":
        obs["series"] = "other"
    elif fault == "missing":
        nodes.pop()
    elif fault == "extra":
        nodes.append({"tag": "FIGURE", "data_src": "https://example.com/extra"})
    elif fault == "order":
        nodes.reverse()
    elif fault == "duplicate":
        nodes.append(copy.deepcopy(nodes[0]))
    elif fault == "wrong_presentation":
        nodes[0] = {"tag": "A", "href": plan["links"][0]["url"], "text": "関連資料"}
    elif fault == "unknown_node":
        nodes[0]["tag"] = "IFRAME"
    elif fault == "empty_nodes":
        obs["footer"]["nodes"] = []
    elif fault == "bad_review_time":
        plan["review"]["reviewed_at"] = "2026-01-01T00:00:00"
    elif fault == "future_review_time":
        plan["review"]["reviewed_at"] = "2099-01-01T00:00:00+00:00"
    elif fault == "missing_registry":
        plan["links"][0]["registry_ref"] = ""
        reviewed(plan)
    elif fault == "duplicate_plan_url":
        plan["links"].append(copy.deepcopy(plan["links"][0]))
        reviewed(plan)
    elif fault == "bad_required":
        plan["links"][0]["required"] = "true"
        reviewed(plan)
    elif fault == "bad_url":
        plan["links"][0]["url"] = "https://user:password@example.com/"
        reviewed(plan)
    elif fault == "ambiguous_figure":
        nodes[1]["hrefs"].append("https://example.com/other")
    code, payload = run_checker(tmp_path, obs)
    assert (
        code == 1 and payload["ok"] is False and payload["ready_for_publish"] is False
    )


def test_optional_omission_and_text_link_pass(tmp_path):
    obs = ready_observation()
    plan = obs["production_plan"]
    plan["links"][1]["required"] = False
    plan["links"][0]["presentation"] = "text_link"
    reviewed(plan)
    obs["footer"]["nodes"] = [
        {"tag": "A", "href": plan["links"][0]["url"], "text": "関連資料"}
    ]
    code, payload = run_checker(tmp_path, obs)
    assert code == 0 and payload["ok"] is True
    assert payload["ready_for_publish"] is False


def test_explicit_bad_plan_does_not_fallback(tmp_path):
    path = tmp_path / "observation.json"
    path.write_text(json.dumps(ready_observation()), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/note_editor_prepublish_verify.py"),
            str(path),
            "--production-plan",
            str(tmp_path / "absent.md"),
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2 and json.loads(result.stdout)["ok"] is False


def run_with_plan(tmp_path, markdown, *, footer_only=False):
    obs = ready_observation()
    obs.pop("production_plan")
    if footer_only:
        obs = {key: obs[key] for key in ("article_id", "series", "footer")}
    op = tmp_path / "observed.json"
    op.write_text(json.dumps(obs), encoding="utf-8")
    pp = tmp_path / "production-pack.md"
    pp.write_text(markdown, encoding="utf-8")
    args = [
        sys.executable,
        str(ROOT / "scripts/note_editor_prepublish_verify.py"),
        str(op),
        "--production-plan",
        str(pp),
        "--json",
    ]
    if footer_only:
        args.append("--footer-only")
    result = subprocess.run(args, capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout)


def test_existing_markdown_plan_publication_footer_entry(tmp_path):
    block = (
        "## Plan\n\n```footer-selection\n" + json.dumps(selection_plan()) + "\n```\n"
    )
    code, payload = run_with_plan(tmp_path, block, footer_only=True)
    assert code == 0 and payload["ok"] is True
    assert (
        payload["live_dom_verified"] is False and payload["ready_for_publish"] is False
    )


@pytest.mark.parametrize(
    "markup", ["missing", "duplicate", "nested", "duplicate_json_key"]
)
def test_markdown_plan_input_failures(tmp_path, markup):
    block = "```footer-selection\n" + json.dumps(selection_plan()) + "\n```\n"
    if markup == "missing":
        block = "## Plan\n"
    elif markup == "duplicate":
        block += block
    elif markup == "nested":
        block = "````text\n" + block + "````\n"
    else:
        block = block.replace(
            '"article_id":', '"article_id": "first", "article_id":', 1
        )
    code, payload = run_with_plan(tmp_path, block, footer_only=True)
    assert code == 2 and payload["ok"] is False


def test_all_optional_links_can_be_omitted(tmp_path):
    obs = ready_observation()
    for link in obs["production_plan"]["links"]:
        link["required"] = False
    reviewed(obs["production_plan"])
    obs["footer"]["nodes"] = []
    code, payload = run_checker(tmp_path, obs)
    assert code == 0 and payload["ok"] is True
    assert payload["ready_for_publish"] is False


def omitted_footer_observation() -> dict:
    obs = ready_observation()
    plan = obs["production_plan"]
    plan.update(decision="omit", reason="本文内で読後行動が完結する", links=[])
    reviewed(plan)
    obs["footer"]["nodes"] = []
    return obs


def test_human_approved_footer_omission_passes(tmp_path):
    code, payload = run_checker(tmp_path, omitted_footer_observation())
    assert code == 0 and payload["issues"] == []
    assert payload["ready_for_publish"] is False
    assert payload["live_dom_verified"] is False


@pytest.mark.parametrize("fault,expected_code", [
    ("missing_decision", "footer_plan_links_missing"),
    ("unknown_decision", "footer_plan_decision_invalid"),
    ("missing_reason", "footer_plan_decision_invalid"),
    ("unapproved", "footer_plan_unapproved"),
    ("changed_reason", "footer_review_hash_mismatch"),
    ("missing_links", "footer_plan_links_missing"),
    ("links_on_omit", "footer_plan_decision_mismatch"),
    ("nodes_on_omit", "footer_extra_url"),
    ("missing_nodes", "footer_nodes_missing"),
    ("include_empty_links", "footer_plan_links_missing"),
])
def test_footer_omission_rejects_missing_or_conflicting_evidence(tmp_path, fault, expected_code):
    obs = omitted_footer_observation()
    plan = obs["production_plan"]
    if fault == "missing_decision":
        plan.pop("decision")
    elif fault == "unknown_decision":
        plan["decision"] = "unknown"
    elif fault == "missing_reason":
        plan.pop("reason")
    elif fault == "unapproved":
        plan["review"]["status"] = "pending"
    elif fault == "changed_reason":
        plan["reason"] = "採用理由を変更"
    elif fault == "missing_links":
        plan.pop("links")
    elif fault == "links_on_omit":
        plan["links"] = selection_plan()["links"]
    elif fault == "nodes_on_omit":
        obs["footer"]["nodes"] = ready_observation()["footer"]["nodes"]
    elif fault == "missing_nodes":
        obs["footer"].pop("nodes")
    elif fault == "include_empty_links":
        plan["decision"] = "include"
    if fault not in {"unapproved", "changed_reason"}:
        reviewed(plan)
    code, payload = run_checker(tmp_path, obs)
    assert code == 1 and expected_code in issue_codes(payload)


def test_explicit_include_preserves_required_link_check(tmp_path):
    obs = ready_observation()
    plan = obs["production_plan"]
    plan.update(decision="include", reason="次の資料へ案内する")
    reviewed(plan)
    code, payload = run_checker(tmp_path, obs)
    assert code == 0 and payload["ok"] is True
    obs["footer"]["nodes"].pop()
    code, payload = run_checker(tmp_path, obs)
    assert code == 1 and "footer_required_missing" in issue_codes(payload)


def test_conflicting_legacy_footer_is_rejected(tmp_path):
    obs = ready_observation()
    obs["footer"]["raw_counts"] = {"https://automata-lab.example/": 1}
    code, payload = run_checker(tmp_path, obs)
    assert code == 1
    assert "footer_legacy_or_unknown_fields" in issue_codes(payload)


def test_footer_manual_boundary_blocks_matching_snapshot(tmp_path):
    obs = ready_observation()
    obs["manual_boundaries"] = {"footer": "要実測"}
    code, payload = run_checker(tmp_path, obs)
    assert code == 1 and "footer_manual_boundary_unverified" in issue_codes(payload)


def test_missing_nodes_is_not_optional_empty_observation(tmp_path):
    obs = ready_observation()
    for link in obs["production_plan"]["links"]:
        link["required"] = False
    reviewed(obs["production_plan"])
    obs["footer"].pop("nodes")
    code, payload = run_checker(tmp_path, obs)
    assert code == 1 and "footer_nodes_missing" in issue_codes(payload)
