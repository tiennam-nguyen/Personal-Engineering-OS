"""Strict payload validation and deterministic IDs for three learning aggregates."""

from __future__ import annotations

import hashlib

from peos.domain.errors import ValidationError
from peos.domain.learning.model import DIMENSIONS

_KEYS = {
    "learning.goal": {"schema_version", "goal", "concept_graph", "diagnostic", "gaps", "plan"},
    "learning.attempt": {
        "schema_version",
        "goal_ref",
        "exercise_id",
        "focus_concept_id",
        "dimension",
        "submitted_raw",
        "submitted_normalized",
        "verifier_kind",
        "correct",
        "feedback_classification",
        "evidence_timestamp",
        "run_id",
    },
    "learning.mastery": {
        "schema_version",
        "goal_ref",
        "attempt_ref",
        "focus_concept_id",
        "dimensions",
        "review_recommendation",
        "derivation_policy",
    },
    "learning.exercise": {
        "schema_version",
        "concept_id",
        "concept_title",
        "dimension",
        "prompt",
        "estimated_minutes",
        "answer",
        "origin",
    },
}


def learning_id(run_id: str, type_: str, ordinal: int) -> str:
    return (
        "art_"
        + hashlib.sha256(f"{run_id}:learning:1.0.0:{type_}:{ordinal}".encode()).hexdigest()[:32]
    )


def validate_learning_payload(type_: str, payload: object) -> None:
    if (
        not isinstance(payload, dict)
        or set(payload) != _KEYS[type_]
        or payload["schema_version"] != 1
    ):
        raise ValidationError("Learning artifact payload fields are invalid.")
    if type_ == "learning.goal":
        if (
            not isinstance(payload["gaps"], list)
            or not isinstance(payload["plan"], dict)
            or not payload["plan"].get("first_exercise")
        ):
            raise ValidationError("Learning goal evidence or plan is invalid.")
    elif type_ == "learning.attempt":
        if (
            payload["dimension"] not in DIMENSIONS
            or payload["feedback_classification"] not in {"correct", "incorrect_answer"}
            or not isinstance(payload["correct"], bool)
        ):
            raise ValidationError("Learning attempt evidence is invalid.")
    elif type_ == "learning.mastery":
        dimensions = payload["dimensions"]
        if not isinstance(dimensions, list) or [
            item.get("dimension") for item in dimensions if isinstance(item, dict)
        ] != list(DIMENSIONS):
            raise ValidationError("Learning mastery requires exactly five ordered dimensions.")
        if any(
            set(item) != {"dimension", "status", "evidence_refs", "basis"}
            or item["status"] not in {"DEMONSTRATED", "NEEDS_WORK", "NOT_ASSESSED"}
            for item in dimensions
        ):
            raise ValidationError("Learning mastery dimension evidence is invalid.")
        retention = dimensions[-1]
        if retention["status"] != "NOT_ASSESSED":
            raise ValidationError("Same-session work cannot demonstrate retention.")
        review = payload["review_recommendation"]
        if (
            not isinstance(review, dict)
            or set(review)
            != {"policy", "policy_version", "based_on_attempt", "interval_days", "due_at", "status"}
            or review["policy"] != "fixed_interval"
            or review["policy_version"] != 1
            or review["status"] != "recommended"
        ):
            raise ValidationError("Learning review recommendation is invalid.")
    else:
        answer, origin = payload["answer"], payload["origin"]
        if (
            payload["dimension"] != "application"
            or any(
                not isinstance(payload[key], str) or not payload[key].strip()
                for key in ("concept_id", "concept_title", "prompt")
            )
            or not isinstance(payload["estimated_minutes"], int)
            or payload["estimated_minutes"] <= 0
            or not isinstance(answer, dict)
            or set(answer) != {"kind", "accepted"}
            or answer["kind"] != "exact_text"
            or not isinstance(answer["accepted"], list)
            or not answer["accepted"]
            or not isinstance(origin, dict)
            or set(origin)
            != {
                "kind",
                "project_packet_id",
                "project_packet_revision",
                "failure_evidence_hash",
                "verification_provenance",
                "failed_check",
                "expected_behavior",
                "observed_behavior",
                "reported_by",
            }
            or origin["kind"] != "project_failure"
            or origin["verification_provenance"] != "reported"
            or not isinstance(origin["failure_evidence_hash"], str)
            or not origin["failure_evidence_hash"].startswith("sha256:")
        ):
            raise ValidationError("Standalone learning exercise payload is invalid.")
