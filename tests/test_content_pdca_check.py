from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_preview_and_pre_publish_on_clean_draft(tmp_path: Path):
    draft = tmp_path / "draft.md"
    draft.write_text(
        "# テスト記事\n\n"
        "これは公開前検査のためのローカル下書きです。十分な本文量を確保し、"
        "非公開情報や秘密情報を含めず、読者に伝える内容を確認するための文章です。"
        "さらに段落を重ねて、短すぎる下書きの警告を避けます。"
        "公開前に見るべき観点として、タイトル、導入、読後の変化、根拠の必要な主張、"
        "リンク、画像、タグ、非公開情報の混入有無を順に確認します。"
        "このサンプルは実公開用ではなく、ローカル検査が過剰に失敗しないことを確かめるためのものです。"
        "読み手にとって自然な導入、本文の流れ、結論までを最低限そろえ、公開直前に人間が確認する"
        "材料として破綻していない長さを持たせています。\n\n"
        "## 本文\n\n"
        "検証用の本文です。根拠が必要な断定は入れず、公開前に確認する観点を整理します。"
        "読者に何を約束するか、どの順番で説明するか、公開後にどの反応を見るかを、"
        "下書き段階で確認できる形にしています。さらに、タグや画像の検討、リンクの確認、"
        "本文中の表現の一貫性を人間が見直せるように、余白を残した文章にしています。"
        "この段階では公開や外部共有を行わず、ローカルの検査だけで安全に閉じます。\n",
        encoding="utf-8",
    )

    preview = tmp_path / "preview.html"
    result = run_script("scripts/note_preview.py", str(draft), "-o", str(preview))
    assert result.returncode == 0, result.stderr
    assert preview.exists()

    result = run_script("scripts/pre_publish_check.py", str(draft), "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"overall": "ok"' in result.stdout


def test_fact_check_reports_uncertain_markers(tmp_path: Path):
    draft = tmp_path / "draft.md"
    draft.write_text("# 記事\n\nこれは未確認の数字 123件 を含む下書きです。\n", encoding="utf-8")
    result = run_script("scripts/note_fact_check.py", "local", str(draft), "--json")
    assert result.returncode == 0
    assert "uncertain_claim" in result.stdout
    assert "number_or_percent" in result.stdout


def test_fact_check_reports_personal_experience_and_source_markers(tmp_path: Path):
    draft = tmp_path / "draft.md"
    draft.write_text(
        "# 記事\n\n"
        "僕がやってみた時に気づいたこととして書いている。\n"
        "出典ノート: 会話ログと体験メモを確認する。\n",
        encoding="utf-8",
    )
    result = run_script("scripts/note_fact_check.py", "local", str(draft), "--json")
    assert result.returncode == 0
    assert "personal_experience_claim" in result.stdout
    assert "source_provenance_marker" in result.stdout


def test_note_diff_check_blocks_localhost_without_fetch(tmp_path: Path):
    draft = tmp_path / "draft.md"
    draft.write_text("# 記事\n\n公開前の差分確認用テキストです。\n", encoding="utf-8")

    result = run_script(
        "scripts/note_diff_check.py",
        "http://localhost:9999/private",
        str(draft),
        "--json",
    )

    assert result.returncode == 0
    assert '"overall": "blocked"' in result.stdout
    assert '"reason": "local_host_blocked"' in result.stdout
    assert '"external_fetch_performed": false' in result.stdout


def test_note_diff_check_blocks_private_ip_without_fetch(tmp_path: Path):
    draft = tmp_path / "draft.md"
    draft.write_text("# 記事\n\n公開前の差分確認用テキストです。\n", encoding="utf-8")

    result = run_script(
        "scripts/note_diff_check.py",
        "http://127.0.0.1:9999/private",
        str(draft),
        "--json",
    )

    assert result.returncode == 0
    assert '"overall": "blocked"' in result.stdout
    assert '"reason": "private_or_local_ip_blocked"' in result.stdout
    assert '"external_fetch_performed": false' in result.stdout
