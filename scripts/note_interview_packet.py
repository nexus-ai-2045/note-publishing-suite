#!/usr/bin/env python3
"""不足している本人情報だけを、少数の選択式質問へ変換する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from note_authorship_gate import evaluate

BASE_QUESTIONS = [
    {
        "id": "reader",
        "question": "この記事を、まず誰に届けたいですか？",
        "choices": ["予備知識ゼロの初学者", "AIには詳しいが制御は初見の人", "研究発表を追いきれなかった人"],
    },
    {
        "id": "tone",
        "question": "文章の雰囲気はどれに寄せますか？",
        "choices": ["普段の口調で一緒に迷う", "落ち着いた入門解説", "イベント参加レポート寄り"],
    },
    {
        "id": "cta",
        "question": "読後に、どんな反応がほしいですか？",
        "choices": ["感想と分かりにくかった箇所", "誤り・バグ報告", "改善案や関連資料", "全部"],
    },
]


def build_packet(draft: Path, evidence: Path | None, max_questions: int, answers: dict[str, object] | None = None) -> dict[str, object]:
    max_questions = max(1, min(max_questions, 5))
    gate = evaluate(draft, evidence)
    answer_map = (answers or {}).get("answers", {})
    if not isinstance(answer_map, dict):
        raise ValueError("answers.answers must be an object")
    answered = set(answer_map)
    questions = [question for question in BASE_QUESTIONS if question["id"] not in answered]
    if gate["unresolved_count"] and "authorship_confirmation" not in answered:
        excerpts = [item["excerpt"] for item in gate["unresolved"][:8]]
        questions.insert(0, {
            "id": "authorship_confirmation",
            "question": "次の本人語りは、実際の発言・体験として残してよいですか？ 不正確なものは直してください。",
            "choices": ["すべて本人の言葉として残す", "一部を直す", "本人語りを外して事実説明にする"],
            "excerpts": excerpts,
        })
    return {
        "schema_version": "note-interview-packet/v1",
        "draft": str(draft),
        "question_count": min(len(questions), max_questions),
        "questions": questions[:max_questions],
        "unresolved_authorship_count": gate["unresolved_count"],
        "generation_rule": "未回答を本人の感想・体験として補完しない",
        "reuse_sources": ["data/note_drafts.json", "data/published_notes.json"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--max-questions", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--answers", type=Path)
    args = parser.parse_args()
    answers = json.loads(args.answers.read_text(encoding="utf-8")) if args.answers else None
    packet = build_packet(args.draft, args.evidence, args.max_questions, answers)
    rendered = json.dumps(packet, ensure_ascii=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
