#!/usr/bin/env python3
"""日本語完了報告ゲートの契約を確認する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_TERMS = {
    "package.yaml": [
        "output_language_gate:",
        "user_visible_language: japanese",
        "cli_status_translation_required: true",
        "japanese_closeout_language_gate",
        "forbidden_untranslated_status_terms:",
    ],
    "SKILL.md": [
        "日本語完了報告ゲート",
        "output_language_gate",
        "ready for review",
        "下書き解除済み",
        "open PR",
        "未マージPR",
        "MERGED",
        "マージ済み",
        "mergeable",
        "マージ可能",
        "success",
        "成功",
        "failed",
        "失敗",
    ],
    "README.md": [
        "構造バグ",
        "出力ゲート",
        "下書き解除済み",
        "未マージPR",
        "マージ済み",
        "マージ可能",
        "コマンド、ファイルパス、URL、SHA",
        "scripts/japanese_closeout_language_check.py --json",
    ],
}

FORBIDDEN_RAW_STATUS_TERMS = [
    "ready for review",
    "open PR",
    "MERGED",
    "mergeable",
    "statusCheckRollup",
]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def collect_findings() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for relative_path, terms in REQUIRED_TERMS.items():
        text = read_text(relative_path)
        for term in terms:
            if term not in text:
                findings.append(
                    {
                        "path": relative_path,
                        "kind": "missing_required_term",
                        "term": term,
                    }
                )

    package = read_text("package.yaml")
    for term in FORBIDDEN_RAW_STATUS_TERMS:
        if term not in package:
            findings.append(
                {
                    "path": "package.yaml",
                    "kind": "missing_forbidden_term_registry",
                    "term": term,
                }
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    findings = collect_findings()
    result = {
        "ok": not findings,
        "checked_files": sorted(REQUIRED_TERMS),
        "findings": findings,
        "forbidden_raw_status_terms": FORBIDDEN_RAW_STATUS_TERMS,
        "external_actions_performed": [],
        "publication_actions_performed": [],
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif findings:
        print("NG 日本語完了報告ゲート検証に失敗")
        for finding in findings:
            print(f"- {finding['path']}: {finding['kind']}: {finding['term']}")
    else:
        print("OK 日本語完了報告ゲート検証に成功")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
