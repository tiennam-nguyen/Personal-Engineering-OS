from __future__ import annotations

import json
from pathlib import Path

from peos.bootstrap import initialize_workspace


def learning_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    goal = {
        "schema_version": 1,
        "goal_slug": "binary-search-correctness",
        "performance": (
            "Given a sorted array and trace, identify the valid interval and next boundary."
        ),
        "conditions": ["ascending integer array", "inclusive interval convention"],
        "quality_bar": "Preserve the interval invariant and choose the valid update.",
        "deadline": None,
        "review_after_days": 3,
        "time_budget_minutes": 10,
        "sensitivity": "private",
    }
    concepts = [
        {
            "id": "ordered-comparison",
            "title": "Ordered comparison",
            "definition": "Compare values in order.",
            "prerequisites": [],
            "examples": [],
            "counterexamples": [],
            "common_confusions": [],
        },
        {
            "id": "binary-search-interval",
            "title": "Binary search interval",
            "definition": "Maintain the active interval.",
            "prerequisites": ["ordered-comparison"],
            "examples": [],
            "counterexamples": [],
            "common_confusions": [],
        },
        {
            "id": "binary-search-correctness",
            "title": "Binary search correctness",
            "definition": "Preserve the search invariant.",
            "prerequisites": ["binary-search-interval"],
            "examples": [],
            "counterexamples": [],
            "common_confusions": [],
        },
    ]
    tasks = [
        {
            "id": "diag-a",
            "concept_id": "ordered-comparison",
            "dimension": "recall",
            "prompt": "Which relation is ascending?",
            "answer": {
                "kind": "single_choice",
                "options": [{"id": "a", "text": "x <= y"}, {"id": "b", "text": "x > y"}],
                "correct_option_id": "a",
            },
        },
        {
            "id": "diag-b",
            "concept_id": "binary-search-interval",
            "dimension": "explanation",
            "prompt": "Name the active interval.",
            "answer": {"kind": "exact_text", "accepted": ["low through high"]},
        },
        {
            "id": "diag-c",
            "concept_id": "binary-search-correctness",
            "dimension": "discrimination",
            "prompt": "Pick valid update.",
            "answer": {
                "kind": "single_choice",
                "options": [{"id": "a", "text": "low=mid+1"}, {"id": "b", "text": "low=mid"}],
                "correct_option_id": "a",
            },
        },
        {
            "id": "diag-d",
            "concept_id": "binary-search-correctness",
            "dimension": "application",
            "prompt": "Apply update.",
            "answer": {"kind": "exact_text", "accepted": ["low equals mid plus one"]},
        },
    ]
    fixture = {
        "schema_version": 1,
        "target_concept_id": "binary-search-correctness",
        "concepts": concepts,
        "diagnostic_tasks": tasks,
        "responses": [
            {"task_id": "diag-a", "answer": "a"},
            {"task_id": "diag-b", "answer": "entire array"},
            {"task_id": "diag-c", "answer": "a"},
            {"task_id": "diag-d", "answer": "low equals mid plus one"},
        ],
        "exercise_bank": [
            {
                "id": "exercise-interval-1",
                "concept_id": "binary-search-interval",
                "dimension": "explanation",
                "prompt": "State the active interval.",
                "estimated_minutes": 5,
                "answer": {"kind": "exact_text", "accepted": ["low through high"]},
            },
            {
                "id": "exercise-target-1",
                "concept_id": "binary-search-correctness",
                "dimension": "application",
                "prompt": "Apply the update.",
                "estimated_minutes": 5,
                "answer": {"kind": "exact_text", "accepted": ["low equals mid plus one"]},
            },
        ],
    }
    goal_path, fixture_path = tmp_path / "goal.json", tmp_path / "diagnostic.json"
    goal_path.write_text(json.dumps(goal), encoding="utf-8")
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    return workspace, goal_path, fixture_path
