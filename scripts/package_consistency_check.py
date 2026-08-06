#!/usr/bin/env python3
"""package 正本と配布コピーの整合、および宣言と実態の一致を検査する。

背景:
    standalone public package では package 自身だけを検査する。
    embedded/private 運用で正本と agent skill コピーの一致も確認する場合は、
    `--skill-copy` でコピー先を明示する。
    `docs/repo-layout.md` の規約は「差分は package 正本へ回収する」。
    しかし手動同期では双方向にドリフトし、静かに機能を失う。

    2026-08 に実際に発生した事象:
      - skill コピーにだけ新規 script が 9 本存在し、正本に無かった
      - 正本にだけ検査パターンが存在し、skill コピーに無かった
      - script が実在するのに package.yaml が宣言しておらず、
        宣言ベースで作られる配布物から欠落していた

検査する不変条件:
    1. `scripts/` 配下の実体が package.yaml の existing_scripts に宣言されている
    2. 宣言されたファイルが実在する
    3. `--skill-copy` 指定時だけ、正本とskillコピーが一致する

改行コードについて:
    Windows 環境では LF / CRLF が混在し、内容が同一でも差分に見える。
    実質差分だけを見るため、比較前に復帰文字を除去する。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 同期対象から外す。実行時生成物と、コピー側に置かない運用ファイル。
EXCLUDED_NAMES = {"__pycache__", ".git"}
EXCLUDED_SUFFIXES = {".pyc"}


def is_excluded(relative: Path) -> bool:
    """比較対象外かを判定する。"""
    if any(part in EXCLUDED_NAMES for part in relative.parts):
        return True
    return relative.suffix in EXCLUDED_SUFFIXES


def collect_files(base: Path) -> set[Path]:
    """base 配下の比較対象ファイルを相対パスで集める。"""
    if not base.is_dir():
        return set()
    found = set()
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(base)
        if not is_excluded(relative):
            found.add(relative)
    return found


def read_normalized(path: Path) -> bytes:
    """改行コード差を無視するため復帰文字を除いて読む。"""
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def check_copy_sync(skill_copy: Path) -> list[dict[str, str]]:
    """正本と skill コピーの一致を検査する。"""
    findings: list[dict[str, str]] = []
    if not skill_copy.is_dir():
        return [{"kind": "missing_skill_copy", "path": str(skill_copy)}]

    canonical = collect_files(ROOT)
    copied = collect_files(skill_copy)

    for relative in sorted(canonical - copied):
        findings.append({"kind": "missing_in_skill_copy", "path": relative.as_posix()})
    for relative in sorted(copied - canonical):
        findings.append({"kind": "missing_in_canonical", "path": relative.as_posix()})
    for relative in sorted(canonical & copied):
        if read_normalized(ROOT / relative) != read_normalized(skill_copy / relative):
            findings.append({"kind": "content_differs", "path": relative.as_posix()})
    return findings


def declared_scripts() -> tuple[set[str], list[dict[str, str]]]:
    """package.yaml の existing_scripts 宣言を読む。

    PyYAML に依存しないよう、対象ブロックだけを行単位で読む。
    """
    package_path = ROOT / "package.yaml"
    if not package_path.exists():
        return set(), [{"kind": "missing_package_yaml", "path": "package.yaml"}]

    declared: set[str] = set()
    in_block = False
    for line in package_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("existing_scripts:"):
            in_block = True
            continue
        if in_block:
            stripped = line.strip()
            if stripped.startswith("- "):
                declared.add(stripped[2:].strip())
                continue
            # インデントの無い次のキーでブロック終了
            if line and not line[0].isspace():
                break
    return declared, []


def check_declaration() -> list[dict[str, str]]:
    """scripts/ の実体と package.yaml の宣言が一致するかを検査する。"""
    declared, findings = declared_scripts()
    if findings:
        return findings

    scripts_dir = ROOT / "scripts"
    actual = {
        f"scripts/{path.name}"
        for path in scripts_dir.glob("*.py")
        # テストは verification の pytest が拾うため宣言対象外
        if not path.name.startswith("test_")
    }
    actual |= {f"scripts/{path.name}" for path in scripts_dir.glob("*.ps1")}

    for missing in sorted(actual - declared):
        findings.append({"kind": "undeclared_script", "path": missing})
    for stale in sorted(declared - actual):
        if not (ROOT / stale).exists():
            findings.append({"kind": "declared_but_absent", "path": stale})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--skill-copy",
        type=Path,
        help="任意。embedded/private運用で内容一致を検査するskillコピーの明示パス。",
    )
    args = parser.parse_args()

    sync_findings = check_copy_sync(args.skill_copy) if args.skill_copy else []
    declaration_findings = check_declaration()
    findings = sync_findings + declaration_findings

    result = {
        "ok": not findings,
        "skipped": False,
        "canonical": str(ROOT.name),
        "copy_sync_checked": args.skill_copy is not None,
        "copy_sync_findings": sync_findings,
        "declaration_findings": declaration_findings,
        "external_actions_performed": [],
        "publication_actions_performed": [],
    }
    if args.skill_copy is not None:
        result["skill_copy"] = args.skill_copy.as_posix()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif findings:
        print("NG package 整合検証に失敗")
        for finding in findings:
            print(f"- {finding['kind']}: {finding['path']}")
        print("修復: 差分を正本へ回収し、正本から skill コピーへ同期する")
    else:
        print("OK package 整合検証に成功")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
