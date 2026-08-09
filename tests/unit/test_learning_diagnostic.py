from __future__ import annotations

from peos.domain.learning.diagnostic import normalize_exact_text, verify_answer


def test_exact_text_and_choice_are_deterministic() -> None:
    assert normalize_exact_text("  LOW\tThrough HIGH ") == "low through high"
    assert (
        verify_answer(
            {"kind": "exact_text", "accepted": ["low through high"]}, " LOW  through high "
        )["correct"]
        is True
    )
    assert (
        verify_answer(
            {
                "kind": "single_choice",
                "options": [{"id": "a", "text": "yes"}],
                "correct_option_id": "a",
            },
            "a",
        )["correct"]
        is True
    )
