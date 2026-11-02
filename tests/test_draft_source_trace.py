"""Checks for listing draft sentences that are not in the author's own words."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.draft_source_trace import draft_sentences, evaluate, ledger_sources, to_markdown


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "Claudeのスキルを6件呼べるようになった。正直ちょっと怪しいと思っている。"


def test_sentence_from_original_is_not_listed():
    result = evaluate("Claudeのスキルを6件呼べるようになった。\n", [SOURCE])
    assert result["sentence_count"] == 1
    assert result["unsourced_sentences"] == []


def test_sentence_the_author_never_said_is_listed_with_line():
    draft = "# 見出し\n\nClaudeのスキルを6件呼べるようになった。これは業界全体を変える革命です。\n"
    result = evaluate(draft, [SOURCE])
    assert result["unsourced_count"] == 1
    row = result["unsourced_sentences"][0]
    assert row["line"] == 3
    assert row["text"] == "これは業界全体を変える革命です。"


def test_skips_front_matter_code_headings_quotes_and_markers():
    draft = ("---\ntitle: 架空の題\n---\n## 見出しは数えない\n> 引用は数えない文章です。\n"
             "<!-- topic: a -->\n```\nコードの中の文章も数えない。\n```\n")
    assert draft_sentences(draft) == []


def test_link_text_is_kept_and_url_dropped():
    sentences = draft_sentences("詳しくは[公式の発表](https://example.com/a)を読んだ。\n")
    assert sentences[0]["text"] == "詳しくは公式の発表を読んだ。"


def test_ledger_counts_author_words_but_not_ai_suggestions():
    ledger = {"topics": [
        {"origin": "user_speech", "evidence": "正直ちょっと怪しいと思っている"},
        {"origin": "ai_suggestion", "evidence": "これは業界全体を変える革命です",
         "author_explanation": "自分の言葉だと、使えるものが増えた感じ"},
    ]}
    sources = ledger_sources(ledger)
    assert "これは業界全体を変える革命です" not in sources
    result = evaluate("これは業界全体を変える革命です。使えるものが増えた感じ。\n", sources)
    assert [row["text"] for row in result["unsourced_sentences"]] == ["これは業界全体を変える革命です。"]


def test_markdown_lists_each_sentence_for_the_author():
    result = evaluate("これは業界全体を変える革命です。\n", [SOURCE])
    text = to_markdown(result)
    assert "# 原文にない文の一覧" in text
    assert "- [ ] 1行目" in text


def test_cli_writes_list_and_requires_a_source(tmp_path):
    draft = tmp_path / "note-body.md"
    draft.write_text("これは業界全体を変える革命です。\n", encoding="utf-8")
    source = tmp_path / "source.txt"
    source.write_text(SOURCE, encoding="utf-8")
    listing = tmp_path / "unsourced.md"
    script = ROOT / "scripts/draft_source_trace.py"
    done = subprocess.run([sys.executable, str(script), str(draft), "--source", str(source),
                           "--markdown", str(listing)], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0
    assert json.loads(done.stdout)["unsourced_count"] == 1
    assert "革命" in listing.read_text(encoding="utf-8")
    missing = subprocess.run([sys.executable, str(script), str(draft)],
                             capture_output=True, text=True, encoding="utf-8")
    assert missing.returncode == 1


def test_author_reaction_counts_but_wall_bounce_ai_answer_does_not():
    ledger = {"topics": [{"origin": "ai_accepted", "evidence": "reply 7",
                          "ai_answer": "収入が止まる不安の方が先に来る", "author_reaction": "確かにそれはある"}]}
    sources = ledger_sources(ledger)
    assert sources == ["確かにそれはある"]
