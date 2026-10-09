#!/usr/bin/env python3
"""供給されたnote観測と承認済み選定計画を照合する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from note_editor_session_check import validate_edit_session

from note_footer_selection import (
    load_production_plan,
    parse_json,
    validate_footer_selection,
)


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

def tag_operation_preflight(readback: Any, article_id: str, account: str) -> dict[str, Any]:
    """trusted runtimeの操作直前DOM読戻しを照合する。候補を採用扱いせず、操作は行わない。"""
    reasons = []
    value = as_dict(readback)
    baseline, current = as_dict(value.get("baseline")), as_dict(value.get("current"))
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
    if not reasons:
        baseline_tags = set(map(normalize_tag, baseline["selected_tags"]))
        selected = set(map(normalize_tag, current["selected_tags"]))
        if baseline_tags != selected:
            reasons.append("tag_selected_changed_since_baseline")
    selected = set(map(normalize_tag, current.get("selected_tags", []))) if not reasons else set()
    return dict(status="blocked" if reasons else "approved", reasons=reasons,
                additions=[] if reasons else [t for t in planned if normalize_tag(t) not in selected],
                skipped=[] if reasons else [t for t in planned if normalize_tag(t) in selected],
                automation_allowed=False)

def validate_tag_preflight(data: dict[str, Any]) -> list[dict[str, str]]:
    if "tag_preflight" not in data:
        return []
    result = tag_operation_preflight(data["tag_preflight"], text_value(data.get("note_id")), text_value(data.get("account")))
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


def validate_tags(data: dict[str, Any]) -> list[dict[str, str]]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for tag in as_list(data.get("tags")):
        normalized = normalize_tag(tag)
        if not normalized:
            continue
        if normalized in seen:
            duplicates.add(normalized)
        seen.add(normalized)
    if not duplicates:
        return []
    return [
        issue(
            "error",
            "duplicate_tags",
            "重複タグが観測されています: " + ", ".join(sorted(duplicates)),
        )
    ]


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


def build_result(
    data: dict[str, Any], production_plan: Any = None, *, footer_only: bool = False
) -> dict[str, Any]:
    issues, manual_boundaries = validate_footer(data, production_plan)
    if not footer_only:
        top_issues, top_boundaries = validate_top_image(data)
        issues.extend(top_issues)
        issues.extend(validate_toc(data))
        issues.extend(validate_magazine(data))
        issues.extend(validate_tags(data))
        issues.extend(validate_tag_preflight(data))
        issues.extend(validate_article_type(data))
        issues.extend(validate_final_buttons(data))
        issues.extend(validate_edit_session(data))
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
        result = build_result(data, plan, footer_only=args.footer_only)
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
