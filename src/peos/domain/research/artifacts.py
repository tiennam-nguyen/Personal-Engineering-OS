"""Strict payload validation and deterministic research artifact IDs."""

from __future__ import annotations

import hashlib

from peos.domain.errors import ValidationError

_KEYS = {
    "research.question": {"question", "scope", "success_criterion", "assumptions"},
    "research.source": {
        "ordinal",
        "input_path",
        "media_type",
        "size_bytes",
        "object_hash",
        "object_locator",
        "acquired_at",
        "acquisition_method",
        "trust",
        "coverage",
    },
    "research.claim": {
        "proposition",
        "semantic_key",
        "polarity",
        "evidence_status",
        "evidence_refs",
    },
    "research.contradiction": {"semantic_key", "positive_claim_id", "negative_claim_id", "reason"},
    "research.synthesis": {
        "question_id",
        "source_ids",
        "claim_ids",
        "contradiction_ids",
        "supported_claim_ids",
        "contested_claim_ids",
        "unreadable_segment_count",
        "generation_method",
    },
}


def validate_research_payload(type_: str, payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != _KEYS[type_]:
        raise ValidationError("Research artifact payload fields are invalid.")
    if type_ == "research.claim":
        if (
            payload["polarity"] not in {"positive", "negative"}
            or payload["evidence_status"] not in {"SUPPORTED", "CONTESTED"}
            or not payload["evidence_refs"]
        ):
            raise ValidationError("Research claim payload is invalid.")
    if (
        type_ == "research.contradiction"
        and payload["reason"] != "opposite_polarity_same_semantic_key"
    ):
        raise ValidationError("Research contradiction payload is invalid.")
    if (
        type_ == "research.synthesis"
        and payload["generation_method"] != "deterministic_traceable_synthesis_v1"
    ):
        raise ValidationError("Research synthesis payload is invalid.")


def research_id(run_id: str, kind: str, suffix: str) -> str:
    return "art_" + hashlib.sha256(f"{run_id}:{kind}:{suffix}".encode()).hexdigest()[:32]
