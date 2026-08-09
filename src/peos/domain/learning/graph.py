"""Dependency-free prerequisite validation and deterministic gap ordering."""

from __future__ import annotations

from typing import Any

from peos.domain.errors import LearningGraphInvalid
from peos.domain.learning.model import LearningGoalInput

JsonObject = dict[str, Any]


def analyze_graph(concepts: list[JsonObject], target: str) -> JsonObject:
    prerequisites = {item["id"]: tuple(item["prerequisites"]) for item in concepts}
    visiting: set[str] = set()
    visited: set[str] = set()
    order: list[str] = []

    def visit(node: str) -> None:
        if node in visiting:
            raise LearningGraphInvalid("Learning prerequisite graph contains a cycle.")
        if node in visited:
            return
        visiting.add(node)
        for prerequisite in prerequisites[node]:
            visit(prerequisite)
        visiting.remove(node)
        visited.add(node)
        order.append(node)

    for concept in concepts:
        visit(str(concept["id"]))
    closure: set[str] = set()

    def collect(node: str) -> None:
        for prerequisite in prerequisites[node]:
            if prerequisite not in closure:
                closure.add(prerequisite)
                collect(prerequisite)

    collect(target)
    depths: dict[str, int] = {}
    for node in order:
        depths[node] = (
            0 if not prerequisites[node] else max(depths[item] for item in prerequisites[node]) + 1
        )
    edges = [
        {"prerequisite": prerequisite, "dependent": concept["id"]}
        for concept in concepts
        for prerequisite in concept["prerequisites"]
    ]
    return {
        "acyclic": True,
        "topological_order": order,
        "prerequisite_closure": [item["id"] for item in concepts if item["id"] in closure],
        "depths": depths,
        "edges": edges,
    }


def derive_plan(
    goal: LearningGoalInput,
    fixture: JsonObject,
    diagnostic: JsonObject,
    graph: JsonObject,
) -> JsonObject:
    states = {item["concept_id"]: item for item in diagnostic["concept_states"]}
    concept_order = {item["id"]: index for index, item in enumerate(fixture["concepts"])}
    gaps = []
    for concept_id in graph["prerequisite_closure"]:
        state = states[concept_id]
        if state["status"] != "DEMONSTRATED":
            gaps.append(
                {
                    "concept_id": concept_id,
                    "reason": "diagnostic_failure"
                    if state["status"] == "NEEDS_WORK"
                    else "not_assessed",
                    "prerequisite_depth": graph["depths"][concept_id],
                    "diagnostic_evidence_refs": state["task_refs"],
                    "selected": False,
                }
            )
    gaps.sort(
        key=lambda item: (
            item["prerequisite_depth"],
            0 if item["reason"] == "diagnostic_failure" else 1,
            concept_order[item["concept_id"]],
            item["concept_id"],
        )
    )
    if gaps:
        gaps[0]["selected"] = True
    focus = gaps[0]["concept_id"] if gaps else fixture["target_concept_id"]
    eligible = [
        item
        for item in fixture["exercise_bank"]
        if item["concept_id"] == focus and item["estimated_minutes"] <= goal.time_budget_minutes
    ]
    if not eligible:
        from peos.domain.errors import LearningExerciseUnavailable

        raise LearningExerciseUnavailable(
            "No deterministic exercise fits the selected concept and time budget."
        )
    practice = [item["concept_id"] for item in gaps] or [fixture["target_concept_id"]]
    events = [
        {
            "concept_id": item,
            "kind": "retrieval",
            "recommended_after_days": goal.review_after_days,
            "reason": "future evidence is required",
        }
        for item in practice
    ]
    exercise = eligible[0]
    return {
        "gaps": gaps,
        "practice_concepts": practice,
        "first_exercise": exercise,
        "future_events": events,
        "selection_reason": "foundational unresolved prerequisite first"
        if gaps
        else "no prerequisite gap; target concept practice",
    }
