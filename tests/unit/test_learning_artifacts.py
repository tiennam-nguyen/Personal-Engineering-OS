from __future__ import annotations

import pytest

from peos.domain.artifacts.validation import ARTIFACT_TYPES
from peos.domain.errors import ValidationError
from peos.domain.learning.artifacts import validate_learning_payload


def test_exactly_three_learning_types_are_registered() -> None:
    assert {item for item in ARTIFACT_TYPES if item.startswith("learning.")} == {
        "learning.goal",
        "learning.attempt",
        "learning.mastery",
    }


def test_learning_payload_unknown_fields_and_retention_fail_closed() -> None:
    with pytest.raises(ValidationError):
        validate_learning_payload("learning.goal", {"schema_version": 1, "extra": True})
    dimensions = [
        {"dimension": name, "status": "NOT_ASSESSED", "evidence_refs": [], "basis": "none"}
        for name in ("recall", "explanation", "discrimination", "application", "retention")
    ]
    dimensions[-1]["status"] = "DEMONSTRATED"
    with pytest.raises(ValidationError):
        validate_learning_payload(
            "learning.mastery",
            {
                "schema_version": 1,
                "goal_ref": {},
                "attempt_ref": {},
                "focus_concept_id": "c",
                "dimensions": dimensions,
                "review_recommendation": {},
                "derivation_policy": "v1",
            },
        )
