#!/usr/bin/env python3
"""Validate figure captions and concept/figure/detail ordering in Note drafts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def validate(data: dict[str, Any]) -> list[dict[str, str]]:
    if data.get("article_lane") != "production_candidate":
        return []

    errors: list[dict[str, str]] = []
    figures = data.get("figures")
    contracts = data.get("concept_contracts")
    if not isinstance(figures, list):
        return [issue("figure_observation_missing", "figuresの実測が必要です")]
    if not isinstance(contracts, list):
        return [issue("concept_contracts_missing", "concept_contractsの実測が必要です")]

    figure_ids: set[str] = set()
    for figure in figures:
        if not isinstance(figure, dict):
            errors.append(issue("figure_observation_invalid", "figureはobjectで記録してください"))
            continue
        figure_id = str(figure.get("id") or "").strip()
        if figure_id:
            figure_ids.add(figure_id)
        if not str(figure.get("caption") or "").strip():
            errors.append(issue("figure_caption_missing", f"図 {figure_id or 'unknown'} のキャプションが空です"))
        if str(figure.get("caption_tag") or "").casefold() != "figcaption":
            errors.append(issue("figure_caption_tag_invalid", f"図 {figure_id or 'unknown'} は実figcaptionを使っていません"))
        previous = figure.get("previous_block")
        if isinstance(previous, dict) and str(previous.get("tag") or "").casefold() == "p" and previous.get("text_empty") is True:
            errors.append(issue("empty_paragraph_before_figure", f"図 {figure_id or 'unknown'} の直前に空段落があります"))

    for contract in contracts:
        if not isinstance(contract, dict):
            errors.append(issue("concept_contract_invalid", "concept_contractはobjectで記録してください"))
            continue
        concept = str(contract.get("concept") or "unknown")
        mention_id = str(contract.get("first_mention_block_id") or "")
        figure_id = str(contract.get("figure_id") or "")
        detail_id = str(contract.get("detail_block_id") or "")
        order = contract.get("block_order")
        expected = [mention_id, figure_id, detail_id]
        if figure_id not in figure_ids or not all(expected):
            errors.append(issue("concept_figure_detail_reference_missing", f"{concept} のblock参照が不足しています"))
        if order != expected:
            errors.append(issue("concept_figure_detail_order_invalid", f"{concept} は初出→図→詳細説明の順ではありません"))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("observation", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.observation.read_text(encoding="utf-8"))
    errors = validate(data)
    payload = {
        "ok": not errors,
        "ready_for_draft_save": not errors,
        "issues": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.json else 2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
