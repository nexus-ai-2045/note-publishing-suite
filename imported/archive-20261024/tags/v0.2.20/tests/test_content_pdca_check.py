from __future__ import annotations

import importlib.util
import json
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


def load_script_module(script_name: str):
    spec = importlib.util.spec_from_file_location(
        script_name.removesuffix(".py"),
        ROOT / "scripts" / script_name,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_pre_publish_reports_caramel_future_date_fixture():
    result = run_script(
        "scripts/pre_publish_check.py",
        "content/drafts/caramel-future-date-prepublish-fixture.md",
        "--json",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    issue_codes = {issue["code"] for issue in payload["issues"]}
    assert payload["overall"] == "warning"
    assert "future_dated_claim" in issue_codes
    assert "publish_time_recheck_required" in issue_codes


def test_local_qa_proof_records_future_date_guard(tmp_path: Path):
    output = tmp_path / "proof.json"
    result = run_script(
        "scripts/run_local_draft_qa_proof.py",
        "content/drafts/caramel-future-date-prepublish-fixture.md",
        "--output",
        str(output),
        "--json",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["overall"] == "stopped_before_publish"
    assert payload["publication_gate"]["state"] == "stopped_before_publish"
    assert "future_date_guard" in payload["publication_gate"]["stop_causes"]
    assert "future_dated_claim" in {
        issue["code"] for issue in payload["pre_publish_issues"]
    }


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


def test_note_diff_check_uses_rendered_note_body_for_caramel_note_url(
    tmp_path: Path, monkeypatch, capsys
):
    note_diff_check = load_script_module("note_diff_check.py")
    phrase = "Caramel の公開本文でだけ見えるレンダリング後の確認文です。"
    draft = tmp_path / "caramel-draft.md"
    draft.write_text(
        "# Caramel 公開確認\n\n"
        "raw HTML ではなく、note.com のレンダリング後本文で比較します。\n\n"
        f"{phrase}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        note_diff_check,
        "fetch_text",
        lambda _url: "<html><body>raw shell only</body></html>",
    )
    monkeypatch.setattr(
        note_diff_check,
        "fetch_rendered_note_body",
        lambda _url: f"Caramel rendered article body\n{phrase}",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "note_diff_check.py",
            "https://note.com/caramel_fixture/n/n123456789abc",
            str(draft),
            phrase,
            "--json",
        ],
    )

    assert note_diff_check.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall"] == "ok"
    assert payload["fetch_method"] == "rendered_note_body"
    assert payload["checks"] == [
        {"phrase": phrase, "in_draft": True, "in_page": True}
    ]


def test_fetch_rendered_note_body_invokes_fetch_note_body_js(monkeypatch):
    note_diff_check = load_script_module("note_diff_check.py")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="Caramel body", stderr="")

    monkeypatch.setattr(note_diff_check.subprocess, "run", fake_run)

    assert note_diff_check.fetch_rendered_note_body("https://note.com/caramel/n/n123") == "Caramel body"
    command, kwargs = calls[0]
    assert command[0] == "node"
    assert command[1].endswith("scripts\\fetch_note_body.js") or command[1].endswith(
        "scripts/fetch_note_body.js"
    )
    assert command[2] == "https://note.com/caramel/n/n123"
    assert kwargs["cwd"] == note_diff_check.ROOT


def test_local_draft_qa_proof_records_rendered_diff_fetch_method(tmp_path: Path):
    qa_proof = load_script_module("run_local_draft_qa_proof.py")
    draft = tmp_path / "caramel-draft.md"
    preview = tmp_path / "caramel.preview.html"
    draft.write_text("# Caramel\n\n本文です。\n", encoding="utf-8")
    preview.write_text("<h1>Caramel</h1>", encoding="utf-8")

    evidence = qa_proof.build_evidence(
        draft=draft,
        preview=preview,
        note_url="https://note.com/caramel/n/n123",
        phrases=["Caramel の確認文"],
        steps=[
            {"label": "note_preview", "exit_code": 0, "parsed_json": None},
            {"label": "pre_publish_check", "exit_code": 0, "parsed_json": {"overall": "ok"}},
            {
                "label": "note_fact_check",
                "exit_code": 0,
                "parsed_json": {"finding_count": 0, "findings": []},
            },
            {
                "label": "note_diff_check",
                "exit_code": 0,
                "parsed_json": {
                    "overall": "ok",
                    "fetch_method": "rendered_note_body",
                    "checks": [],
                },
            },
        ],
    )

    assert evidence["diff_check"]["fetch_method"] == "rendered_note_body"
    assert evidence["diff_fetch_method"] == "rendered_note_body"
    assert evidence["qa_lane"] == "return_to_draft"
    assert "human_review_required" in evidence["publication_gate"]["stop_causes"]
