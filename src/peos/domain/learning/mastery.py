"""Independent multidimensional mastery evidence and review policy."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from peos.domain.learning.model import DIMENSIONS

JsonObject = dict[str, Any]


def derive_mastery(
    goal_payload: JsonObject,
    attempt_ref: JsonObject,
    verification: JsonObject,
    attempt_time: datetime,
) -> JsonObject:
    focus = goal_payload["plan"]["first_exercise"]["concept_id"]
    results = [
        item for item in goal_payload["diagnostic"]["task_results"] if item["concept_id"] == focus
    ]
    dimensions = []
    for name in DIMENSIONS:
        evidence = [
            f"diagnostic:{item['task_id']}" for item in results if item["dimension"] == name
        ]
        matching = [item for item in results if item["dimension"] == name]
        status = (
            "NOT_ASSESSED"
            if not matching
            else "NEEDS_WORK"
            if any(not item["correct"] for item in matching)
            else "DEMONSTRATED"
        )
        if name == verification["dimension"]:
            status = "DEMONSTRATED" if verification["correct"] else "NEEDS_WORK"
            evidence.append(f"attempt:{attempt_ref['id']}@{attempt_ref['revision']}")
        if name == "retention":
            status, evidence = "NOT_ASSESSED", []
        dimensions.append(
            {
                "dimension": name,
                "status": status,
                "evidence_refs": evidence,
                "basis": "deterministic diagnostic and attempt evidence"
                if evidence
                else "no supported evidence",
            }
        )
    due = attempt_time + timedelta(days=goal_payload["goal"]["review_after_days"])
    return {
        "focus_concept_id": focus,
        "dimensions": dimensions,
        "review_recommendation": {
            "policy": "fixed_interval",
            "policy_version": 1,
            "based_on_attempt": attempt_ref,
            "interval_days": goal_payload["goal"]["review_after_days"],
            "due_at": due.isoformat().replace("+00:00", "Z"),
            "status": "recommended",
        },
        "derivation_policy": "deterministic_multidimensional_v1",
    }
