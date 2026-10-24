from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/note_authorship_gate.py"


def run_gate(source: Path, draft: Path, *args: str) -> tuple[int, dict]:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(draft),
            "--source",
            str(source),
            "--json",
            *args,
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.stdout, result.stderr
    return result.returncode, json.loads(result.stdout)


def write_pair(tmp_path: Path, source_text: str, draft_text: str) -> tuple[Path, Path]:
    source = tmp_path / "source.md"
    draft = tmp_path / "draft.md"
    source.write_text(source_text, encoding="utf-8")
    draft.write_text(draft_text, encoding="utf-8")
    return source, draft


def test_existing_cli_without_source_remains_compatible(tmp_path: Path):
    draft = tmp_path / "draft.md"
    draft.write_text("これは一般的な説明です。", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(draft), "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["overall"] == "ok"


def test_missing_meaning_paragraph_fails_closed(tmp_path: Path):
    source, draft = write_pair(
        tmp_path,
        "最初にボートで予測制御を理解します。\n\n風と波の不確実さも観測します。",
        "最初にボートで予測制御を理解します。",
    )
    returncode, payload = run_gate(source, draft)
    assert returncode == 1
    assert payload["shortening"]["overall"] == "blocked"
    assert payload["shortening"]["missing_paragraph_count"] == 1


def test_paragraph_reduction_over_budget_fails_closed(tmp_path: Path):
    source, draft = write_pair(
        tmp_path,
        "観測した現在地から複数の操作候補を予測し、制約を守る候補を比較します。",
        "観測した現在地から操作候補を予測します。",
    )
    returncode, payload = run_gate(source, draft, "--shortening-budget", "0.20")
    assert returncode == 1
    assert payload["shortening"]["over_budget_paragraph_count"] == 1


def test_reduction_within_budget_and_preserved_major_phrase_passes(tmp_path: Path):
    source, draft = write_pair(
        tmp_path,
        "観測した現在地から複数の操作候補を予測し、制約を守る候補を比較します。",
        "観測した現在地から操作候補を予測し、制約を守る候補を比較します。",
    )
    returncode, payload = run_gate(
        source,
        draft,
        "--shortening-budget",
        "0.30",
        "--major-phrase",
        "制約を守る候補",
    )
    assert returncode == 0
    assert payload["shortening"]["overall"] == "ok"


def test_missing_major_phrase_fails_even_when_length_is_similar(tmp_path: Path):
    source, draft = write_pair(
        tmp_path,
        "予測・最適化・一歩実行・再計算を繰り返します。",
        "予測・最適化・全体実行・再計算を繰り返します。",
    )
    returncode, payload = run_gate(
        source,
        draft,
        "--shortening-budget",
        "0.20",
        "--major-phrase",
        "一歩実行",
    )
    assert returncode == 1
    assert payload["shortening"]["missing_major_phrases"] == ["一歩実行"]


def test_production_candidate_without_source_and_budget_fails_closed(tmp_path: Path):
    draft = tmp_path / "draft.md"
    draft.write_text(
        "---\narticle_lane: production_candidate\n---\n\n公開候補の本文です。\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(draft), "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["shortening"]["checked"] is False
    assert set(payload["shortening"]["stop_causes"]) == {
        "production_shortening_source_required",
        "production_shortening_budget_required",
    }


def test_production_frontmatter_resolves_unique_source_and_budget(tmp_path: Path):
    source = tmp_path / "interview-packet.md"
    source.write_text("残すべき本人の説明と具体例です。", encoding="utf-8")
    draft = tmp_path / "draft.md"
    draft.write_text(
        "---\n"
        "article_lane: production_candidate\n"
        "shortening_source: interview-packet.md\n"
        "shortening_budget: 0.10\n"
        "---\n\n"
        "残すべき本人の説明と具体例です。\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(draft), "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, payload
    assert payload["shortening"]["checked"] is True
    assert payload["shortening"]["source_resolution"] == "frontmatter"
    assert payload["shortening"]["shortening_budget"] == 0.1


def test_production_conflicting_cli_and_frontmatter_source_fails_closed(tmp_path: Path):
    frontmatter_source = tmp_path / "interview-packet.md"
    cli_source = tmp_path / "other-source.md"
    frontmatter_source.write_text("本人の説明です。", encoding="utf-8")
    cli_source.write_text("別の説明です。", encoding="utf-8")
    draft = tmp_path / "draft.md"
    draft.write_text(
        "---\narticle_lane: production_candidate\n"
        "shortening_source: interview-packet.md\nshortening_budget: 0.10\n---\n\n"
        "本人の説明です。\n",
        encoding="utf-8",
    )
    returncode, payload = run_gate(
        cli_source, draft, "--shortening-budget", "0.10"
    )
    assert returncode == 1
    assert payload["shortening"]["checked"] is False
    assert payload["shortening"]["stop_causes"] == [
        "ambiguous_shortening_source"
    ]
