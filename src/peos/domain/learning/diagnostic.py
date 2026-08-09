"""Pure deterministic answer and diagnostic evidence."""

from __future__ import annotations

import re
from typing import Any

from peos.domain.errors import LearningAttemptInvalid

JsonObject = dict[str, Any]


def normalize_exact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def verify_answer(answer_key: JsonObject, submitted: str) -> JsonObject:
    if answer_key["kind"] == "exact_text":
        normalized = normalize_exact_text(submitted)
        correct = normalized in {normalize_exact_text(item) for item in answer_key["accepted"]}
        expected: object = [normalize_exact_text(item) for item in answer_key["accepted"]]
    else:
        option_ids = {item["id"] for item in answer_key["options"]}
        if submitted not in option_ids:
            raise LearningAttemptInvalid("Submitted choice option is invalid.")
        normalized = submitted
        correct = submitted == answer_key["correct_option_id"]
        expected = answer_key["correct_option_id"]
    return {
        "submitted_raw": submitted,
        "submitted_normalized": normalized,
        "verifier_kind": answer_key["kind"],
        "correct": correct,
        "expected_representation": expected,
    }


def analyze_diagnostic(fixture: JsonObject) -> JsonObject:
    responses = {item["task_id"]: item["answer"] for item in fixture["responses"]}
    results = []
    for task in fixture["diagnostic_tasks"]:
        verified = verify_answer(task["answer"], responses[task["id"]])
        results.append(
            {
                "task_id": task["id"],
                "concept_id": task["concept_id"],
                "dimension": task["dimension"],
                **verified,
            }
        )
    states = []
    for concept in fixture["concepts"]:
        evidence = [item for item in results if item["concept_id"] == concept["id"]]
        status = (
            "NOT_ASSESSED"
            if not evidence
            else "NEEDS_WORK"
            if any(not item["correct"] for item in evidence)
            else "DEMONSTRATED"
        )
        states.append(
            {
                "concept_id": concept["id"],
                "status": status,
                "task_refs": [item["task_id"] for item in evidence],
            }
        )
    return {"task_results": results, "concept_states": states}
