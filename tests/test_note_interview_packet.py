#!/usr/bin/env python3
"""Interview packet question routing tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from note_interview_packet import build_packet  # noqa: E402


def write_draft(tmp_path: Path, text: str) -> Path:
    draft = tmp_path / "draft.md"
    draft.write_text(text, encoding="utf-8")
    return draft


def test_unverified_personal_claim_is_first_question(tmp_path: Path) -> None:
    draft = write_draft(tmp_path, "私は今回試して役に立った。\n")

    packet = build_packet(draft, None, 5)

    assert packet["unresolved_authorship_count"] == 1
    assert packet["questions"][0]["id"] == "authorship_confirmation"
    assert packet["questions"][0]["excerpts"] == ["私は今回試して役に立った。"]


def test_answered_base_questions_are_not_asked_again(tmp_path: Path) -> None:
    draft = write_draft(tmp_path, "制御理論の入門記事です。\n")
    answers = {"answers": {"reader": "予備知識ゼロの初学者", "tone": "落ち着いた入門解説"}}

    packet = build_packet(draft, None, 5, answers)

    assert [question["id"] for question in packet["questions"]] == ["cta"]
    assert packet["question_count"] == 1


def test_question_limit_is_clamped_to_supported_range(tmp_path: Path) -> None:
    draft = write_draft(tmp_path, "制御理論の入門記事です。\n")

    minimum = build_packet(draft, None, 0)
    maximum = build_packet(draft, None, 99)

    assert minimum["question_count"] == 1
    assert len(minimum["questions"]) == 1
    assert maximum["question_count"] == 3
    assert len(maximum["questions"]) == 3


def test_packet_keeps_no_invention_rule(tmp_path: Path) -> None:
    draft = write_draft(tmp_path, "制御理論の入門記事です。\n")

    packet = build_packet(draft, None, 5)

    assert packet["generation_rule"] == "未回答を本人の感想・体験として補完しない"


def test_answered_authorship_confirmation_is_not_repeated(tmp_path: Path) -> None:
    draft = write_draft(tmp_path, "私は今回試して役に立った。\n")
    answers = {"answers": {"authorship_confirmation": "一部を直す"}}

    packet = build_packet(draft, None, 5, answers)

    assert "authorship_confirmation" not in [question["id"] for question in packet["questions"]]


def test_non_object_answers_are_rejected(tmp_path: Path) -> None:
    draft = write_draft(tmp_path, "制御理論の入門記事です。\n")

    with pytest.raises(ValueError, match="answers.answers must be an object"):
        build_packet(draft, None, 5, {"answers": []})
