from __future__ import annotations

from datetime import UTC, datetime

from peos.domain.learning.mastery import derive_mastery


def test_mastery_is_multidimensional_and_retention_is_not_assessed() -> None:
    goal = {
        "goal": {"review_after_days": 3},
        "plan": {"first_exercise": {"concept_id": "c"}},
        "diagnostic": {
            "task_results": [
                {"task_id": "d", "concept_id": "c", "dimension": "explanation", "correct": False}
            ]
        },
    }
    result = derive_mastery(
        goal,
        {"id": "art_a", "revision": "sha256:a"},
        {"dimension": "explanation", "correct": True},
        datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert [item["dimension"] for item in result["dimensions"]] == [
        "recall",
        "explanation",
        "discrimination",
        "application",
        "retention",
    ]
    assert result["dimensions"][1]["status"] == "DEMONSTRATED"
    assert result["dimensions"][-1]["status"] == "NOT_ASSESSED"
    assert "score" not in result and "mastered" not in result
    assert result["review_recommendation"]["due_at"] == "2026-01-04T00:00:00Z"
