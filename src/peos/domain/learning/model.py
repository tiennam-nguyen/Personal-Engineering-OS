"""Strict storage-neutral Learning Compiler input contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from peos.domain.errors import LearningInputInvalid

DIMENSIONS = ("recall", "explanation", "discrimination", "application", "retention")
ASSESSED_DIMENSIONS = frozenset(DIMENSIONS[:-1])


@dataclass(frozen=True)
class LearningGoalInput:
    goal_slug: str
    performance: str
    conditions: tuple[str, ...]
    quality_bar: str
    deadline: str | None
    review_after_days: int
    time_budget_minutes: int
    sensitivity: str


JsonObject = dict[str, Any]


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LearningInputInvalid(f"{field} must be non-empty text.")
    return value.strip()


def parse_goal_input(value: object) -> LearningGoalInput:
    keys = {
        "schema_version",
        "goal_slug",
        "performance",
        "conditions",
        "quality_bar",
        "deadline",
        "review_after_days",
        "time_budget_minutes",
        "sensitivity",
    }
    if not isinstance(value, dict) or set(value) != keys or value["schema_version"] != 1:
        raise LearningInputInvalid("Learning goal fields are invalid.")
    slug = _text(value["goal_slug"], "goal_slug")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise LearningInputInvalid("Learning goal slug is invalid.")
    conditions = value["conditions"]
    if (
        not isinstance(conditions, list)
        or not conditions
        or not all(isinstance(item, str) and item.strip() for item in conditions)
    ):
        raise LearningInputInvalid("Learning goal conditions are invalid.")
    deadline = value["deadline"]
    if deadline is not None:
        deadline = _text(deadline, "deadline")
        try:
            parsed = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        except ValueError as error:
            raise LearningInputInvalid("Learning deadline is invalid.") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise LearningInputInvalid("Learning deadline must be timezone-aware.")
    review, budget = value["review_after_days"], value["time_budget_minutes"]
    if (
        not isinstance(review, int)
        or isinstance(review, bool)
        or review <= 0
        or not isinstance(budget, int)
        or isinstance(budget, bool)
        or budget <= 0
    ):
        raise LearningInputInvalid("Learning cadence and time budget must be positive integers.")
    if value["sensitivity"] not in {"public", "private", "confidential"}:
        raise LearningInputInvalid("Learning sensitivity is invalid.")
    return LearningGoalInput(
        slug,
        _text(value["performance"], "performance"),
        tuple(item.strip() for item in conditions),
        _text(value["quality_bar"], "quality_bar"),
        deadline,
        review,
        budget,
        str(value["sensitivity"]),
    )


def parse_diagnostic_fixture(value: object) -> JsonObject:
    keys = {
        "schema_version",
        "target_concept_id",
        "concepts",
        "diagnostic_tasks",
        "responses",
        "exercise_bank",
    }
    if not isinstance(value, dict) or set(value) != keys or value["schema_version"] != 1:
        raise LearningInputInvalid("Diagnostic fixture fields are invalid.")
    concepts = _records(
        value["concepts"],
        {
            "id",
            "title",
            "definition",
            "prerequisites",
            "examples",
            "counterexamples",
            "common_confusions",
        },
        "concept",
    )
    ids = [str(item["id"]) for item in concepts]
    if not ids or len(ids) != len(set(ids)) or value["target_concept_id"] not in ids:
        raise LearningInputInvalid("Concept identities or target are invalid.")
    for concept in concepts:
        prerequisites = concept["prerequisites"]
        if (
            not isinstance(prerequisites, list)
            or len(prerequisites) != len(set(prerequisites))
            or any(item not in ids or item == concept["id"] for item in prerequisites)
        ):
            raise LearningInputInvalid("Concept prerequisite references are invalid.")
        for field in ("examples", "counterexamples", "common_confusions"):
            if not isinstance(concept[field], list):
                raise LearningInputInvalid("Concept examples/confusions are invalid.")
        _text(concept["title"], "concept.title")
        _text(concept["definition"], "concept.definition")
    tasks = _records(
        value["diagnostic_tasks"],
        {"id", "concept_id", "dimension", "prompt", "answer"},
        "diagnostic task",
    )
    task_ids = [str(item["id"]) for item in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise LearningInputInvalid("Duplicate diagnostic task IDs are invalid.")
    for task in tasks:
        if task["concept_id"] not in ids or task["dimension"] not in ASSESSED_DIMENSIONS:
            raise LearningInputInvalid("Diagnostic task reference or dimension is invalid.")
        _validate_answer(task["answer"])
    responses = _records(value["responses"], {"task_id", "answer"}, "diagnostic response")
    response_ids = [str(item["task_id"]) for item in responses]
    if len(response_ids) != len(set(response_ids)) or set(response_ids) != set(task_ids):
        raise LearningInputInvalid("Every diagnostic task requires exactly one response.")
    exercises = _records(
        value["exercise_bank"],
        {"id", "concept_id", "dimension", "prompt", "estimated_minutes", "answer"},
        "exercise",
    )
    exercise_ids = [str(item["id"]) for item in exercises]
    if len(exercise_ids) != len(set(exercise_ids)):
        raise LearningInputInvalid("Duplicate exercise IDs are invalid.")
    for exercise in exercises:
        if (
            exercise["concept_id"] not in ids
            or exercise["dimension"] not in ASSESSED_DIMENSIONS
            or not isinstance(exercise["estimated_minutes"], int)
            or exercise["estimated_minutes"] <= 0
        ):
            raise LearningInputInvalid("Exercise reference, dimension, or duration is invalid.")
        _validate_answer(exercise["answer"])
    return {
        "schema_version": 1,
        "target_concept_id": value["target_concept_id"],
        "concepts": concepts,
        "diagnostic_tasks": tasks,
        "responses": responses,
        "exercise_bank": exercises,
    }


def parse_attempt_input(value: object) -> JsonObject:
    keys = {"schema_version", "goal_artifact_id", "goal_revision", "exercise_id", "answer"}
    if not isinstance(value, dict) or set(value) != keys or value["schema_version"] != 1:
        raise LearningInputInvalid("Learning attempt fields are invalid.")
    if not re.fullmatch(r"art_[0-9a-f]{32}", str(value["goal_artifact_id"])) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", str(value["goal_revision"])
    ):
        raise LearningInputInvalid("Learning attempt goal reference is invalid.")
    _text(value["exercise_id"], "exercise_id")
    _text(value["answer"], "answer")
    return dict(value)


def _records(value: object, keys: set[str], name: str) -> list[JsonObject]:
    if not isinstance(value, list) or not value:
        raise LearningInputInvalid(f"{name} records must be non-empty.")
    if not all(isinstance(item, dict) and set(item) == keys for item in value):
        raise LearningInputInvalid(f"{name} fields are invalid.")
    return [dict(item) for item in value]


def _validate_answer(value: object) -> None:
    if not isinstance(value, dict) or value.get("kind") not in {"exact_text", "single_choice"}:
        raise LearningInputInvalid("Deterministic answer kind is invalid.")
    if value["kind"] == "exact_text":
        if (
            set(value) != {"kind", "accepted"}
            or not isinstance(value["accepted"], list)
            or not value["accepted"]
            or not all(isinstance(item, str) and item.strip() for item in value["accepted"])
        ):
            raise LearningInputInvalid("Exact-text answer key is invalid.")
    else:
        if (
            set(value) != {"kind", "options", "correct_option_id"}
            or not isinstance(value["options"], list)
            or not value["options"]
        ):
            raise LearningInputInvalid("Single-choice answer key is invalid.")
        options = value["options"]
        if not all(isinstance(item, dict) and set(item) == {"id", "text"} for item in options):
            raise LearningInputInvalid("Single-choice options are invalid.")
        ids = [item["id"] for item in options]
        if len(ids) != len(set(ids)) or value["correct_option_id"] not in ids:
            raise LearningInputInvalid("Single-choice correct option is invalid.")
