#!/usr/bin/env python3
"""既存research段階から呼ぶ品質契約。資料の意味や承認の真正性は判定しない。"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unicodedata import category

from note_footer_selection import _url as valid_http_url

AREAS = {"seo", "aio", "note", "tags", "pdca", "creator_trends"}
LOOPS = {"article_local", "immediate_publication", "article_outcomes", "topic_portfolio", "strategy"}
KINDS = {"dynamic", "official", "creator"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("調査品質: " + message)


def text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def strings(value: Any) -> bool:
    return isinstance(value, list) and all(text(item) for item in value)


def validate_policy(policy: Any) -> dict:
    require(isinstance(policy, dict), "policyはオブジェクトが必要です")
    require(policy.get("schema_version") == "nps-research-quality-policy/v1", "policyのschemaが不正です")
    require(type(policy.get("required")) is bool, "policy.requiredは真偽値が必要です")
    ages = policy.get("max_age_days")
    require(isinstance(ages, dict) and set(ages) == KINDS, "資料区分ごとのmax_age_daysが必要です")
    require(all(type(days) is int and 0 < days <= 365 for days in ages.values()), "鮮度日数は1〜365の整数が必要です")
    return policy


def check_quality_report(raw: bytes, policy: dict, *, article_id: str, base_dir: Path,
                         feedback_refs: set[str], now: datetime | None = None) -> dict[str, str]:
    """保存済み資料を読戻す。HTTP取得や別の承認・完了台帳は作らない。"""
    from note_workflow_gate import parse_packet
    report = parse_packet(raw)
    require(isinstance(report, dict), "reportはJSONオブジェクトが必要です")
    require(report.get("schema_version") == "note-research-quality/v1", "reportのschemaが不正です")
    require(report.get("article_id") == article_id, "reportの記事が一致しません")
    require(text(report.get("topic")), "今回の主題が必要です")
    now = now or datetime.now(timezone.utc)
    require(now.utcoffset() is not None, "検査日時にはtimezoneが必要です")
    sources = report.get("sources")
    require(isinstance(sources, list), "sources配列が必要です")
    evidence_hashes: dict[str, str] = {}
    for source in sources:
        require(isinstance(source, dict), "sourceはオブジェクトが必要です")
        source_id = source.get("id")
        require(text(source_id) and source_id not in evidence_hashes, "資料IDが不足または重複しています")
        require(source.get("kind") in tuple(KINDS), "資料区分が不正です")
        require(all(text(source.get(key)) for key in ("url", "readback", "observed_at", "evidence_path")),
                f"{source_id}: 出典・本文読戻し・観測日時・保存資料が必要です")
        # 末尾カードのHTTP URL検査を再利用し、DEL/C1を含む制御文字も拒否する。
        require(valid_http_url(source["url"])
                and not any(category(char) == "Cc" for char in source["url"]),
                f"{source_id}: 再訪できる出典URLが必要です")
        observed = datetime.fromisoformat(source["observed_at"])
        require(observed.utcoffset() is not None, f"{source_id}: 観測日時にはtimezoneが必要です")
        age = now - observed
        require(timedelta(0) <= age <= timedelta(days=policy["max_age_days"][source["kind"]]),
                f"{source_id}: 観測日時が未来または鮮度切れです")
        evidence_path = Path(source["evidence_path"])
        data = (evidence_path if evidence_path.is_absolute() else base_dir / evidence_path).read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        require(bool(data.strip()) and source.get("evidence_sha256") == actual, f"{source_id}: 保存資料のSHA-256が一致しません")
        evidence_hashes[source_id] = actual
        reuse = source.get("reuse")
        if reuse is not None:
            require(isinstance(reuse, dict) and reuse.get("topic") == report["topic"]
                    and reuse.get("unchanged") is True and text(reuse.get("reason")),
                    f"{source_id}: 再利用には同じ主題・未変更・理由が必要です")
    areas = report.get("areas")
    require(isinstance(areas, dict) and set(areas) == AREAS, "6領域の判定が必要です")
    for name, area in areas.items():
        require(isinstance(area, dict), f"{name}: 判定はオブジェクトが必要です")
        require(area.get("status") in ("pass", "not_applicable"), f"{name}: 確認が完了していません")
        require(text(area.get("reason")) and text(area.get("decision")), f"{name}: 結果の理由と採否案が必要です")
        require(area.get("unresolved") == [], f"{name}: 必須の未解決事項があります")
        ids = area.get("source_ids")
        require(strings(ids) and len(ids) == len(set(ids)) and set(ids) <= evidence_hashes.keys(),
                f"{name}: 資料IDが未確認または重複しています")
        require(area["status"] == "not_applicable" or bool(ids), f"{name}: 確認済み資料が必要です")
    loops = report.get("pdca_loops")
    require(isinstance(loops, list) and len(loops) == len(LOOPS), "5段階のPDCA計画が必要です")
    scopes = set()
    for loop in loops:
        require(isinstance(loop, dict) and loop.get("scope") in tuple(LOOPS), "PDCA段階が不正です")
        require(loop["scope"] not in scopes, "PDCA段階が重複しています")
        scopes.add(loop["scope"])
        require(all(text(loop.get(key)) for key in ("owner", "change", "measure", "when", "feedback_entry_ref")),
                "PDCAには担当・変更・測定対象・測定時期・feedback参照が必要です")
        require(loop["feedback_entry_ref"] in feedback_refs, "PDCAの採否案が既存feedbackに記録されていません")
        require(strings(loop.get("missing_data")) and strings(loop.get("constraints")), "未取得と制約は配列で明示してください")
        require(loop.get("status") in ("planned", "observed"), "PDCAの計画と実測を区別してください")
        if loop["status"] == "observed":
            require(text(loop.get("result")) and text(loop.get("source_id"))
                    and loop["source_id"] in evidence_hashes, "実測には結果と確認済み資料が必要です")
    return evidence_hashes
