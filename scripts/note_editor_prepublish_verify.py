#!/usr/bin/env python3
"""供給されたnote観測と承認済み選定計画を照合する。"""

from __future__ import annotations

import importlib.util

import argparse
from datetime import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_LOADER_SPEC = importlib.util.spec_from_file_location(
    "_nps_loader_bootstrap", Path(__file__).with_name("nps_script_loader.py"))
if _LOADER_SPEC is None or _LOADER_SPEC.loader is None:
    raise ImportError("cannot load NPS script loader")
_LOADER_MODULE = importlib.util.module_from_spec(_LOADER_SPEC)
_LOADER_SPEC.loader.exec_module(_LOADER_MODULE)
_load_sibling_module = _LOADER_MODULE.load_script


validate_edit_session = _load_sibling_module("note_editor_session_check").validate_edit_session

load_production_plan = _load_sibling_module("note_footer_selection").load_production_plan
parse_json = _load_sibling_module("note_footer_selection").parse_json
validate_footer_selection = _load_sibling_module("note_footer_selection").validate_footer_selection


FOOTER_KEYS = ("footer_embeds", "footer_embed_urls", "footer")
TOP_IMAGE_KEYS = ("top_image", "image_upload")


def normalize_tag(tag: Any) -> str:
    return str(tag).strip().lstrip("#").casefold()


def issue(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []



def text_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def validate_previous_tag_comparison(value: Any, article_id: str, article_lane: str) -> list[str]:
    """前話の比較記録を要求し、続き記事では初回扱いを許可しない。"""
    if not isinstance(value, dict) or not isinstance(value.get("reference"), str) or not value["reference"].strip():
        return ["tag_previous_reference_missing"]
    if value.get("status") == "none":
        if article_lane == "continuation_article" or not isinstance(value.get("reason"), str) or not value["reason"].strip():
            return ["tag_previous_none_invalid"]
        return []
    tags = value.get("tags")
    if (value.get("status", "previous") != "previous"
            or not isinstance(value.get("article_id"), str) or not value["article_id"].strip()
            or value["article_id"] == article_id
            or not isinstance(value.get("comparison"), str) or not value["comparison"].strip()
            or not isinstance(tags, list) or not tags
            or any(not isinstance(tag, str) or not normalize_tag(tag) for tag in tags)
            or len(set(map(normalize_tag, tags))) != len(tags)):
        return ["tag_previous_comparison_invalid"]
    return []


def _tag_design_entries(rows: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    if not isinstance(rows, list) or not 5 <= len(rows) <= 10:
        errors.append("tag_design_count_invalid")
        rows = []
    names: list[str] = []
    roles: set[str] = set()
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("tag"), str)
                or not normalize_tag(row["tag"])
                or row.get("role") not in ("topic", "context", "series")
                or any(not isinstance(row.get(key), str) or not row[key].strip()
                       for key in ("reason", "evidence_ref"))):
            errors.append("tag_design_entry_invalid")
            continue
        names.append(normalize_tag(row["tag"]))
        roles.add(row["role"])
    if len(names) != len(set(names)):
        errors.append("tag_design_duplicate")
    if roles != {"topic", "context", "series"}:
        errors.append("tag_design_roles_missing")
    return names, errors


def validate_tag_strategy(strategy: Any) -> list[str]:
    """本文との適合・発見性・ブランド方針の選定根拠を欠落させない。"""
    if not isinstance(strategy, dict):
        return ["tag_design_strategy_missing"]
    unresolved = {"pending", "unknown", "todo", "tbd", "none", "null", "n/a",
                  "未確認", "未定", "保留", "確認待ち", "未決定", "未承認", "検討中"}
    errors = []
    for axis in ("content", "discovery", "branding"):
        item = strategy.get(axis)
        if not isinstance(item, dict) or any(
                not isinstance(item.get(field), str) or not item[field].strip()
                or item[field].strip().casefold() in unresolved
                for field in ("reason", "evidence_ref")):
            errors.append(f"tag_design_strategy_invalid:{axis}")
    return errors


def validate_tag_reference_policy(policy: Any) -> list[str]:
    """利用者が採用した参照を定義する。固有のrepo名やpathは埋め込まない。"""
    if (not isinstance(policy, dict) or policy.get("schema") != "nps-tag-reference-policy/v1"
            or type(policy.get("required")) is not bool):
        return ["tag_reference_policy_invalid"]
    sources = policy.get("strategy_sources", {})
    if not policy["required"] and sources == {}:
        return []
    if (not isinstance(sources, dict) or set(sources) != {"content", "discovery", "branding"}
            or any(not isinstance(paths, list) or not paths
                   or any(not isinstance(path, str) or not path.strip() for path in paths)
                   or len(paths) != len(set(paths)) for paths in sources.values())):
        return ["tag_reference_sources_invalid"]
    return []


def validate_tag_reference_readback(design: Any, policy: Any, hashes: Any) -> list[str]:
    """採用資料の現版と検索意図を照合。実閲覧・意味理解の真正性は認定しない。"""
    if policy is None:
        return []
    errors = validate_tag_reference_policy(policy)
    if errors or not policy["required"]:
        return errors
    sources = policy["strategy_sources"]
    paths = {path for values in sources.values() for path in values}
    if not isinstance(hashes, dict) or not paths <= hashes.keys():
        return ["tag_reference_current_sources_missing"]
    value = as_dict(design)
    expected = {path: hashes[path] for path in paths}
    if value.get("reference_readback") != expected:
        errors.append("tag_reference_readback_missing_or_stale")
    strategy = as_dict(value.get("strategy"))
    for axis, permitted in sources.items():
        if as_dict(strategy.get(axis)).get("evidence_ref") not in permitted:
            errors.append(f"tag_strategy_reference_not_adopted:{axis}")
    intents = value.get("search_intents")
    if (not isinstance(intents, list) or not 2 <= len(intents) <= 3
            or any(not isinstance(item, str) or not item.strip() for item in intents)
            or len({item.strip().casefold() for item in intents}) != len(intents)):
        errors.append("tag_search_intents_missing_or_invalid")
    return errors


def validate_tag_design(design: Any, article_id: str, tags: Any, draft_text: Any,
                        *, article_lane: str = "production_candidate",
                        reference_policy: Any = None, reference_hashes: Any = None) -> list[str]:
    """選定根拠を現在本文へ束縛する。分類の意味・本人採用・実選択は自動認定しない。"""
    if not isinstance(design, dict):
        return ["tag_design_missing"]
    errors: list[str] = []
    if (not isinstance(article_id, str) or not article_id.strip()
            or design.get("schema") != "note-tag-design/v1" or design.get("article_id") != article_id):
        errors.append("tag_design_identity_invalid")
    split_frontmatter = _load_sibling_module("pre_publish_check").split_frontmatter
    if not isinstance(draft_text, str) or not draft_text.strip():
        errors.append("tag_design_body_missing")
    else:
        metadata, body = split_frontmatter(draft_text)
        if metadata.get("article_lane") == "continuation_article":
            article_lane = "continuation_article"
        try:
            current_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        except UnicodeError:
            errors.append("tag_design_body_invalid")
        else:
            if design.get("body_sha256") != current_hash:
                errors.append("tag_design_body_mismatch")
    policy = design.get("policy")
    if (not isinstance(policy, dict) or type(policy.get("min_tags")) is not int
            or type(policy.get("max_tags")) is not int
            or policy != {"id": "nps-local-tags/v1", "min_tags": 5, "max_tags": 10}):
        errors.append("tag_design_policy_invalid")
    errors.extend(validate_tag_strategy(design.get("strategy")))
    errors.extend(validate_tag_reference_readback(design, reference_policy, reference_hashes))
    names, entry_errors = _tag_design_entries(design.get("tags"))
    errors.extend(entry_errors)
    if (not isinstance(tags, list) or not tags
            or any(not isinstance(tag, str) or not normalize_tag(tag) for tag in tags)
            or list(map(normalize_tag, tags)) != names):
        errors.append("tag_design_settings_mismatch")
    errors.extend(validate_previous_tag_comparison(design.get("previous_article"), article_id, article_lane))
    return errors

def tag_operation_preflight(readback: Any, article_id: str, account: str, *,
                            expected_tags: Any = None) -> dict[str, Any]:
    """操作前の不変性、または選定済み変更後の完全一致を照合する。権限は発行しない。"""
    reasons = []
    value = as_dict(readback)
    baseline, current = as_dict(value.get("baseline")), as_dict(value.get("current"))
    phase = value.get("phase", "pre_edit")
    if phase not in ("pre_edit", "post_edit"):
        reasons.append("tag_phase_invalid")
    if not article_id or not account:
        reasons.append("tag_identity_missing")
    for label, observed in (("baseline", baseline), ("current", current)):
        if observed.get("article_id") != article_id or observed.get("account") != account:
            reasons.append(f"tag_identity_mismatch:{label}")
        if observed.get("selection_scope_verified") is not True:
            reasons.append(f"tag_selected_region_unverified:{label}")
        for key in ("selected_tags", "suggested_tags"):
            tags = observed.get(key)
            if not isinstance(tags, list) or any(not isinstance(t, str) or not t.strip().lstrip("#") for t in tags):
                reasons.append(f"tag_list_invalid:{label}:{key}")
            elif key == "selected_tags" and len(set(map(normalize_tag, tags))) != len(tags):
                reasons.append(f"tag_selected_duplicate:{label}")
    planned = value.get("planned_additions")
    if not isinstance(planned, list) or any(not isinstance(t, str) or not t.strip().lstrip("#") for t in planned):
        reasons.append("tag_plan_invalid")
        planned = []
    elif len(set(map(normalize_tag, planned))) != len(planned):
        reasons.append("tag_plan_duplicate")
    if phase == "post_edit":
        removals = value.get("planned_removals")
        for label, tags in (("expected", expected_tags), ("removals", removals)):
            if (not isinstance(tags, list)
                    or (label == "expected" and not tags)
                    or any(not isinstance(t, str) or not normalize_tag(t) for t in tags)
                    or len(set(map(normalize_tag, tags))) != len(tags)):
                reasons.append(f"tag_{label}_invalid")
        if not reasons:
            original = set(map(normalize_tag, baseline["selected_tags"]))
            added = set(map(normalize_tag, planned))
            removed = set(map(normalize_tag, removals))
            expected = set(map(normalize_tag, expected_tags))
            selected = set(map(normalize_tag, current["selected_tags"]))
            if added & removed or not removed.issubset(original):
                reasons.append("tag_transition_plan_invalid")
            elif (original - removed) | added != expected:
                reasons.append("tag_transition_design_mismatch")
            if selected != expected:
                reasons.append("tag_selected_design_mismatch")
    elif not reasons:
        baseline_tags = set(map(normalize_tag, baseline["selected_tags"]))
        selected = set(map(normalize_tag, current["selected_tags"]))
        if baseline_tags != selected:
            reasons.append("tag_selected_changed_since_baseline")
    selected = set(map(normalize_tag, current.get("selected_tags", []))) if not reasons else set()
    return dict(status="blocked" if reasons else "approved", reasons=reasons,
                additions=[] if reasons or phase == "post_edit" else [t for t in planned if normalize_tag(t) not in selected],
                skipped=[] if reasons else [t for t in planned if normalize_tag(t) in selected],
                automation_allowed=False)

def validate_tag_preflight(data: dict[str, Any]) -> list[dict[str, str]]:
    if "tag_preflight" not in data:
        return []
    result = tag_operation_preflight(data["tag_preflight"], text_value(data.get("note_id")),
                                     text_value(data.get("account")), expected_tags=data.get("tags"))
    return [issue("error", reason, "タグ操作直前の読戻し不一致。現在値と提案の差を提示し、変更を上書きしない") for reason in result["reasons"]]

def manual_boundary_for(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    boundaries = as_dict(data.get("manual_boundaries"))
    for key in keys:
        value = boundaries.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def validate_top_image(
    data: dict[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    boundaries: list[dict[str, str]] = []
    top_image = as_dict(data.get("top_image"))
    if top_image.get("present") is True:
        return issues, boundaries

    boundary = manual_boundary_for(data, TOP_IMAGE_KEYS)
    if boundary:
        boundaries.append(
            {
                "code": "top_image_manual_boundary",
                "message": boundary,
            }
        )
        return issues, boundaries

    issues.append(
        issue(
            "error",
            "top_image_missing",
            "トップ画像の観測と手動アップロード境界の記録がありません",
        )
    )
    return issues, boundaries


def validate_toc(data: dict[str, Any]) -> list[dict[str, str]]:
    toc_count = data.get("toc_count")
    if isinstance(toc_count, int) and toc_count >= 1:
        return []
    return [
        issue(
            "error",
            "toc_missing",
            "目次が観測されていません",
        )
    ]


def validate_footer(
    data: dict[str, Any], production_plan: Any = None
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    plan = data.get("production_plan") if production_plan is None else production_plan
    issues = validate_footer_selection(data, plan)
    boundaries: list[dict[str, str]] = []
    boundary = manual_boundary_for(data, FOOTER_KEYS)
    if boundary:
        boundaries.append({"code": "footer_embed_manual_boundary", "message": boundary})
        issues.append(
            issue(
                "error",
                "footer_manual_boundary_unverified",
                "フッターの手動確認境界は照合の合格を意味しません",
            )
        )
    return issues, boundaries


def validate_magazine(data: dict[str, Any]) -> list[dict[str, str]]:
    magazine = as_dict(data.get("magazine"))
    if magazine.get("added") is True:
        return []
    return [
        issue(
            "error",
            "magazine_missing",
            "対象マガジンへの追加が観測されていません",
        )
    ]


def validate_tags(data: dict[str, Any], *, reference_policy: Any = None,
                  reference_hashes: Any = None) -> list[dict[str, str]]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for tag in as_list(data.get("tags")):
        normalized = normalize_tag(tag)
        if not normalized:
            continue
        if normalized in seen:
            duplicates.add(normalized)
        seen.add(normalized)
    issues = [] if not duplicates else [
        issue(
            "error",
            "duplicate_tags",
            "重複タグが観測されています: " + ", ".join(sorted(duplicates)),
        )
    ]
    if "tag_design" in data or data.get("stage") in ("settings", "publish"):
        reasons = validate_tag_design(data.get("tag_design"), text_value(data.get("note_id", data.get("article_id"))),
                                      data.get("tags"), data.get("draft_text"),
                                      article_lane=text_value(data.get("article_lane")),
                                      reference_policy=reference_policy, reference_hashes=reference_hashes)
        if data.get("stage") == "publish":
            preflight = tag_operation_preflight(data.get("tag_preflight"), text_value(data.get("note_id")),
                                                text_value(data.get("account")), expected_tags=data.get("tags"))
            reasons.extend(preflight["reasons"])
            current = as_dict(as_dict(data.get("tag_preflight")).get("current"))
            if (not preflight["reasons"] and set(map(normalize_tag, current["selected_tags"]))
                    != set(map(normalize_tag, as_list(data.get("tags"))))):
                reasons.append("tag_selected_design_mismatch")
        issues.extend(issue("error", reason, "タグ設計と本文・設定・実選択を照合できません") for reason in reasons)
    return issues


def validate_article_type(data: dict[str, Any]) -> list[dict[str, str]]:
    article_type = data.get("article_type")
    if isinstance(article_type, str) and article_type.strip():
        return []
    return [
        issue(
            "error",
            "article_type_missing",
            "無料・有料の記事種別が記録されていません",
        )
    ]


def validate_final_buttons(data: dict[str, Any]) -> list[dict[str, str]]:
    buttons = as_list(data.get("final_buttons"))
    if not buttons:
        return [
            issue(
                "error",
                "final_button_state_missing",
                "最終公開ボタンの状態が記録されていません",
            )
        ]

    issues: list[dict[str, str]] = []
    for button in buttons:
        item = as_dict(button)
        if item.get("clicked") is True:
            label = item.get("label") or "unknown"
            issues.append(
                issue(
                    "error",
                    "final_button_clicked",
                    f"最終公開ボタンがクリックされています: {label}",
                )
            )
    return issues


PUBLICATION_ACTION_KEYS = (
    "publication_actions_performed", "external_actions_performed", "public_actions_performed",
)
AUTOMATION_PLAN_KEYS = (
    "automation_actions", "automation_plan", "button_click_plan", "planned_actions", "allowed_actions",
)
PROHIBITED_PUBLICATION_TOKENS = (
    "publish", "schedule", "post", "submit", "send", "share",
    "公開", "投稿", "予約投稿", "送信", "共有", "更新する",
)
READ_ONLY_PUBLICATION_SETTINGS_ACTIONS = frozenset({
    "read_only", "read-only", "open_settings", "settings-open",
    "open_publish_settings", "open_publication_settings", "read_publication_settings",
    "inspect_publish_settings", "公開設定を開く", "公開設定を確認",
})
PREPUBLICATION_SAFE_OPERATIONS = READ_ONLY_PUBLICATION_SETTINGS_ACTIONS | frozenset({"write_draft", "save_draft"})
PREPUBLICATION_SAFE_STATES = frozenset({"draft"})


def validate_human_only_publication_boundary(data: dict[str, Any]) -> list[dict[str, str]]:
    issues = []
    if data.get("manual_publish_required") is not True:
        issues.append(issue("error", "manual_publish_required_missing", "公開は人間が行うという明示が必要です"))
    if data.get("send_button_automation_allowed") is not False:
        issues.append(issue("error", "send_button_automation_allowed", "公開・送信ボタンの自動操作は禁止です"))
    for key in AUTOMATION_PLAN_KEYS:
        actions = data.get(key, [])
        if not isinstance(actions, list):
            issues.append(issue("error", "publication_action_plan_unknown", f"{key}の操作計画が不正です"))
            continue
        for action in actions:
            if not isinstance(action, str) or not action.strip():
                issues.append(issue("error", "publication_action_plan_unknown", f"{key}の操作名が不正です"))
                continue
            operation = action.strip().casefold()
            if operation in PREPUBLICATION_SAFE_OPERATIONS:
                continue
            words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", action.strip()).casefold()
            tokens = re.split(r"[^a-z0-9]+", words)
            if ("post" in tokens
                    or any(token in operation for token in PROHIBITED_PUBLICATION_TOKENS if token.isascii() and token != "post")
                    or any(token in operation for token in PROHIBITED_PUBLICATION_TOKENS if not token.isascii())):
                issues.append(issue("error", "publication_action_in_automation_plan", f"{key}に公開・送信操作があります"))
            else:
                issues.append(issue("error", "publication_action_plan_unknown", f"{key}は許可された正式な下書き操作ではありません"))
    return issues


def validate_identity(data: dict[str, Any]) -> list[dict[str, str]]:
    issues = []
    note_id = data.get("note_id")
    expected = data.get("expected_note_id")
    observed_urls = [(key, data[key]) for key in ("screen_url", "url") if key in data]
    for key, value in (("note_id", note_id), ("expected_note_id", expected), *observed_urls):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            issues.append(issue("error", "note_identity_invalid", f"{key}が不正です"))
    for key, value in (("note_id", note_id), ("expected_note_id", expected)):
        if value is not None and (not isinstance(value, str) or not value.startswith("n")
                                  or not value[1:].isascii() or not value[1:].isalnum()):
            issues.append(issue("error", "note_identity_invalid", f"{key}はNote記事IDである必要があります"))
    if not isinstance(expected, str) or not expected.strip():
        issues.append(issue("error", "expected_note_identity_missing", "期待したNote IDを明示する必要があります"))
    if not note_id and not observed_urls:
        issues.append(issue("error", "note_identity_missing", "観測したNote IDまたはURLが必要です"))
    if expected and note_id and expected != note_id:
        issues.append(issue("error", "note_identity_mismatch", "期待したNote IDと観測したIDが異なります"))
    for key, screen_url in observed_urls:
        try:
            if not isinstance(screen_url, str) or not screen_url.strip():
                raise ValueError("invalid URL")
            parsed = urlsplit(screen_url)
            valid = (parsed.scheme == "https" and parsed.hostname in {"note.com", "editor.note.com"}
                     and not parsed.username and not parsed.password and parsed.port in (None, 443))
            if not valid:
                raise ValueError("unexpected editor URL")
            segments = parsed.path.strip("/").split("/")
            route_note_id = None
            if parsed.hostname == "editor.note.com" and len(segments) == 3 and segments[0] == "notes" and segments[2] == "edit":
                route_note_id = segments[1]
            elif parsed.hostname == "note.com":
                if len(segments) == 3 and segments[1] == "n":
                    route_note_id = segments[2]
                elif len(segments) == 2 and segments[0] == "preview":
                    route_note_id = segments[1]
            if (not route_note_id or not route_note_id.startswith("n")
                    or not route_note_id[1:].isascii() or not route_note_id[1:].isalnum()):
                raise ValueError("URL has no canonical article route")
            if route_note_id != expected:
                issues.append(issue("error", "screen_url_note_mismatch", "画面URLと期待したNote IDが異なります"))
            if note_id and route_note_id != note_id:
                issues.append(issue("error", "screen_url_note_mismatch", "画面URLと観測したNote IDが異なります"))
        except ValueError:
            issues.append(issue("error", "screen_url_note_mismatch", f"{key}のNote記事URLを確認できません"))
    return issues


def validate_save_state(data: dict[str, Any]) -> list[dict[str, str]]:
    if data.get("draft_saved") is True:
        return []
    return [issue("error", "draft_save_state_missing", "draft_saved=trueという明示的な保存確認が必要です")]


def validate_save_readback(data: dict[str, Any]) -> list[dict[str, str]]:
    readback = as_dict(data.get("save_readback"))
    issues = []
    try:
        times = [datetime.fromisoformat(readback[key].replace("Z", "+00:00"))
                 for key in ("saved_at", "observed_at")]
        if any(value.tzinfo is None for value in times):
            raise ValueError("timezone missing")
        if times[1] < times[0]:
            issues.append(issue("error", "post_save_readback_time_invalid", "再読時刻が保存より前です"))
    except (KeyError, TypeError, ValueError, AttributeError):
        issues.append(issue("error", "post_save_readback_missing", "保存・再読の時刻とtimezoneが必要です"))
    if any(readback.get(key) is not True for key in
           ("same_note_id", "reloaded_or_reclaimed", "expected_invariants_verified")):
        issues.append(issue("error", "post_save_readback_incomplete", "同一記事・再読・期待構造の確認が必要です"))
    return issues


def validate_publication_actions(data: dict[str, Any]) -> list[dict[str, str]]:
    issues = []
    for key in PUBLICATION_ACTION_KEYS:
        if key in data and (not isinstance(data[key], list) or data[key]):
            issues.append(issue("error", "publication_or_external_action_recorded", f"{key}は空配列である必要があります"))
    if not any(key in data for key in ("publication_state", "status")):
        issues.append(issue("error", "publication_state_unknown", "公開前の下書き状態を明示する必要があります"))
    for key in ("publication_state", "status"):
        if key not in data:
            continue
        state = data[key]
        if not isinstance(state, str) or not state.strip():
            issues.append(issue("error", "publication_state_unknown", f"{key}の状態を確認できません"))
        elif state.strip().casefold() in {"published", "scheduled", "posted", "public"}:
            issues.append(issue("error", "already_published_or_scheduled", "公開・予約済み状態を公開前合格と扱えません"))
        elif state.strip().casefold() not in PREPUBLICATION_SAFE_STATES:
            issues.append(issue("error", "publication_state_unknown", f"{key}は確認済みの下書き状態ではありません"))
    return issues


def build_result(
    data: dict[str, Any], production_plan: Any = None, *, footer_only: bool = False,
    settings_path: Path | None = None, article_id: str | None = None,
) -> dict[str, Any]:
    data = dict(data)
    expected = {}
    if settings_path is not None:
        expected, _ = _load_sibling_module("note_workflow_gate").read_workspace_settings(settings_path, article_id or "")
        if expected.get("linebreak_policy") is not None:
            data["linebreak_policy"] = expected["linebreak_policy"]
    issues, manual_boundaries = validate_footer(data, production_plan)
    if not footer_only:
        top_issues, top_boundaries = validate_top_image(data)
        issues.extend(top_issues)
        issues.extend(validate_toc(data))
        issues.extend(validate_magazine(data))
        issues.extend(validate_tags(data, reference_policy=expected.get("tag_reference_policy"),
                                    reference_hashes=expected.get("reference_hashes")))
        issues.extend(validate_tag_preflight(data))
        issues.extend(validate_article_type(data))
        issues.extend(validate_final_buttons(data))
        issues.extend(validate_edit_session(data))
        linebreak = _load_sibling_module("note_linebreak_gate")
        if data.get("linebreak_policy") is not None:
            line_errors, _ = linebreak.validate(data)
            issues.extend({"severity": "error", **item} for item in line_errors)
        if data.get("article_lane") in ("production_candidate", "continuation_article"):
            issues.extend(validate_human_only_publication_boundary(data))
            issues.extend(validate_identity(data))
            issues.extend(validate_save_state(data))
            issues.extend(validate_save_readback(data))
            issues.extend(validate_publication_actions(data))
        manual_boundaries.extend(top_boundaries)
    return {
        "ok": not any(item["severity"] == "error" for item in issues),
        "ready_for_publish": False,
        "verification_scope": "supplied_snapshot_only",
        "live_dom_verified": False,
        "issues": issues,
        "manual_boundaries": manual_boundaries,
        "external_actions_performed": [],
        "publication_actions_performed": [],
    }


def load_observation(path: Path) -> dict[str, Any]:
    data = parse_json(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("観測のルートはJSONオブジェクトが必要です")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="供給されたnote観測と承認済み選定計画を照合します。"
    )
    parser.add_argument("observation", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--production-plan", type=Path)
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--article-id")
    parser.add_argument(
        "--footer-only",
        action="store_true",
        help="公開後も供給されたフッター観測だけを照合",
    )
    args = parser.parse_args()

    try:
        data = load_observation(args.observation)
        plan = (
            load_production_plan(args.production_plan)
            if args.production_plan is not None
            else None
        )
        result = build_result(data, plan, footer_only=args.footer_only,
                              settings_path=args.settings, article_id=args.article_id)
    except (OSError, ValueError, TypeError, RecursionError):
        result = {
            "ok": False,
            "ready_for_publish": False,
            "verification_scope": "supplied_snapshot_only",
            "live_dom_verified": False,
            "issues": [
                issue(
                    "error",
                    "input_invalid",
                    "入力を読み取れません。形式・参照ファイル・重複JSONキーを確認してください",
                )
            ],
            "manual_boundaries": [],
            "external_actions_performed": [],
            "publication_actions_performed": [],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        ready = "true" if result["ready_for_publish"] else "false"
        print(f"OK ready_for_publish={ready}")
        for boundary in result["manual_boundaries"]:
            print(f"manual_boundary:{boundary['code']} {boundary['message']}")
    else:
        print("NG")
        for item in result["issues"]:
            print(f"{item['severity']}:{item['code']} {item['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
