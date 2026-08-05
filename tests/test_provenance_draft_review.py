from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sample_draft() -> str:
    return """---
title: 由来レビュー例
source_mode: source_pack_locked_with_user_speech_priority
publication_gate: human_review_required
external_action: none
---
# 由来レビュー例

<!-- provenance
kind: user-said
source: current-conversation
review: keep
-->
## 本人の言葉

私は、下書きで AI 作文を見分けたいと話した。

<!-- provenance
kind: external-fact
source: official-source-pack
review: verify
-->
## 確認済みの外部事実

公式資料で確認した事実。

<!-- provenance
kind: assistant-organized
source: assistant-structure
review: revise
-->
## AI による整理

上の材料を読みやすい順序に並べ替えた。

<!-- provenance
kind: hold
source: needs-review
review: decide
-->
## 未確認

要確認の AI 推測は保留する。
"""


def test_multiline_provenance_blocks_include_review_handles():
    checker = load_script("provenance_label_check")
    _, body, start_line = checker.split_frontmatter(sample_draft())
    blocks, findings = checker.parse_blocks(body, start_line)

    assert findings == []
    assert [block.label for block in blocks] == [
        "user-said",
        "external-fact",
        "assistant-organized",
        "hold",
    ]
    assert blocks[0].review == "keep"
    assert blocks[0].heading == "本人の言葉"
    assert "私は、下書きで" in blocks[0].quote


def test_public_markdown_strips_comments_and_hold_blocks_export(tmp_path: Path):
    checker = load_script("provenance_label_check")
    draft = tmp_path / "draft.md"
    draft.write_text(sample_draft(), encoding="utf-8")

    result = checker.check_draft(draft)
    assert result["ok"] is False
    assert result["publication_ready"] is False
    assert "hold_present" in {item["code"] for item in result["findings"]}

    without_hold = sample_draft().replace(
        """<!-- provenance
kind: hold
source: needs-review
review: decide
-->
## 未確認

要確認の AI 推測は保留する。
""",
        "",
    )
    public_text = checker.strip_provenance_comments(without_hold)
    assert "<!-- provenance" not in public_text
    assert "AI による整理" in public_text


def test_public_markdown_strips_html_comment_bang_end_tag():
    checker = load_script("provenance_label_check")
    text = """<!-- provenance-label: user-said; source: user-speech --!>
本文。
"""

    public_text = checker.strip_provenance_comments(text)

    assert "provenance-label" not in public_text
    assert public_text == "本文。\n"


def test_review_preview_renders_visible_japanese_provenance_labels():
    preview = load_script("note_preview")
    rendered = preview.render_markdown(sample_draft(), review_provenance=True)

    assert "由来: ユーザー発言" in rendered
    assert "由来: 確認済み外部事実" in rendered
    assert "由来: AIによる整理・言い換え" in rendered
    assert "由来: 未確認・人間判断待ち" in rendered
    assert "provenance-card" in rendered


def test_normal_preview_hides_provenance_comments():
    preview = load_script("note_preview")
    rendered = preview.render_markdown(sample_draft())

    assert "provenance" not in rendered
    assert "&lt;!--" not in rendered


def test_review_context_card_exposes_human_friendly_provenance_summary(
    tmp_path: Path,
):
    review = load_script("review_draft")
    draft = tmp_path / "draft.md"
    draft.write_text(
        sample_draft().replace(
            "publication_gate: human_review_required",
            "article_lane: production_candidate\npublication_gate: human_review_required",
        ),
        encoding="utf-8",
    )

    payload = review.review_draft(draft)
    provenance = payload["context_card"]["provenance"]
    assert provenance["counts"]["assistant-organized"] == 1
    assert provenance["hold_count"] == 1
    assert provenance["review_handles"][0]["heading"] == "本人の言葉"
    assert "hold_present" in payload["reason_codes"]
    assert payload["verdict"] == "blocked"


def test_public_output_cli_writes_only_after_hold_is_resolved(tmp_path: Path):
    draft = tmp_path / "draft.md"
    output = tmp_path / "public.md"
    draft.write_text(sample_draft(), encoding="utf-8")

    blocked = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "provenance_label_check.py"),
            str(draft),
            "--public-output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
    )
    assert blocked.returncode == 1
    assert not output.exists()


def test_public_output_cli_omits_draft_frontmatter(tmp_path: Path):
    draft = tmp_path / "draft.md"
    output = tmp_path / "public.md"
    draft.write_text(
        sample_draft().replace(
            """<!-- provenance
kind: hold
source: needs-review
review: decide
-->
## 未確認

要確認の AI 推測は保留する。
""",
            "",
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "provenance_label_check.py"),
            str(draft),
            "--public-output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
    )

    assert completed.returncode == 0
    public_text = output.read_text(encoding="utf-8")
    assert not public_text.startswith("---")
    assert "article_lane:" not in public_text
    assert "source_mode:" not in public_text
    assert "AI による整理" in public_text


def test_project_ssot_does_not_duplicate_package_version():
    ssot = (ROOT / "PROJECT_SSOT.md").read_text(encoding="utf-8")

    assert "パッケージ版:" not in ssot


def test_skills_broaden_article_draft_auto_trigger_and_hide_internal_ids():
    parent = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    draft_skill = (ROOT / "skills" / "note-draft-production" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    combined = "\n".join([parent, draft_skill, readme])

    for phrase in [
        "記事を書いて",
        "文章にまとめて",
        "会話を記事に",
        "メモを記事に",
        "下書きを直して",
        "--review-provenance",
        "--public-output",
        "見出しまたは本文の短い引用",
    ]:
        assert phrase in combined
    assert "B07" not in combined
    assert "B12" not in combined


def test_unknown_provenance_label_fails_closed_without_crashing(tmp_path: Path):
    draft = tmp_path / "unknown.md"
    draft.write_text(
        """---
title: unknown label
source_mode: source_pack_locked_with_user_speech_priority
---
<!-- provenance
kind: invented
source: assistant-structure
review: hold
-->
本文。
""",
        encoding="utf-8",
    )
    checker = load_script("provenance_label_check")

    result = checker.check_draft(draft)

    assert result["ok"] is False
    assert "unknown_label" in {item["code"] for item in result["findings"]}
