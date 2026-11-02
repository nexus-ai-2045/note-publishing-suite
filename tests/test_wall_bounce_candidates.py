"""Checks for picking wall-bounce answers the author seemed to accept."""

from __future__ import annotations

import pytest

from scripts.wall_bounce_candidates import candidates


TURNS = [
    {"role": "user", "text": "AIで仕事なくなるの怖い"},
    {"role": "assistant", "text": "収入が止まる不安の方が先に来るかもしれません"},
    {"role": "user", "text": "確かに、それはある"},
    {"role": "assistant", "text": "では、生活費の話から入るのはどうでしょう"},
    {"role": "user", "text": "じゃあ最初はお金の話なの？"},
    {"role": "assistant", "text": "はい、そう考えています"},
    {"role": "user", "text": "うーん、ちょっと違う"},
]


def test_agreement_and_question_are_listed_but_disagreement_is_not() -> None:
    rows = candidates(TURNS)
    assert [(row["turn"], row["kind"]) for row in rows] == [(2, "accepted"), (4, "question")]
    assert rows[0]["ai_answer"] == "収入が止まる不安の方が先に来るかもしれません"
    assert rows[0]["author_reaction"] == "確かに、それはある"


def test_only_author_turns_right_after_ai_count() -> None:
    turns = [{"role": "user", "text": "なるほど"}, {"role": "user", "text": "確かに"}]
    assert candidates(turns) == []


def test_rejects_non_list() -> None:
    with pytest.raises(ValueError):
        candidates({"role": "user"})
