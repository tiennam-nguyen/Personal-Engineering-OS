from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from peos.bootstrap import open_learning_workspace, open_workspace
from tests.learning_support import learning_workspace


def test_learning_acceptance_fixture_compile_attempt_and_verify(tmp_path: Path) -> None:
    workspace, goal_file, diagnostic_file = learning_workspace(tmp_path)
    service = open_learning_workspace(workspace)
    compiled = service.start_compile(goal_file, diagnostic_file)
    assert compiled["state"] == "SUCCEEDED"
    assert service.verify(str(compiled["run_id"]))["valid"] is True
    refs = cast(list[dict[str, Any]], cast(dict[str, Any], compiled["outputs"])["artifacts"])
    artifacts, _ = open_workspace(workspace)
    goal = artifacts.get(str(refs[0]["artifact_id"]))
    payload = cast(dict[str, Any], goal.artifact.payload)
    assert payload["concept_graph"]["acyclic"] is True
    assert payload["concept_graph"]["prerequisite_closure"] == [
        "ordered-comparison",
        "binary-search-interval",
    ]
    assert payload["gaps"][0]["concept_id"] == "binary-search-interval"
    assert payload["gaps"][0]["reason"] == "diagnostic_failure"
    assert payload["plan"]["first_exercise"]["id"] == "exercise-interval-1"
    attempt_file = tmp_path / "attempt.json"
    attempt_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "goal_artifact_id": goal.artifact.id,
                "goal_revision": goal.artifact.content_hash,
                "exercise_id": "exercise-interval-1",
                "answer": " LOW  through HIGH ",
            }
        )
    )
    attempted = service.start_attempt(goal.artifact.id, attempt_file)
    assert service.verify(str(attempted["run_id"]))["valid"] is True
    attempt_refs = cast(
        list[dict[str, Any]], cast(dict[str, Any], attempted["outputs"])["artifacts"]
    )
    mastery = artifacts.get(str(attempt_refs[1]["artifact_id"]))
    mastery_payload = cast(dict[str, Any], mastery.artifact.payload)
    dimensions = {item["dimension"]: item for item in mastery_payload["dimensions"]}
    assert dimensions["explanation"]["status"] == "DEMONSTRATED"
    assert dimensions["retention"]["status"] == "NOT_ASSESSED"
    assert mastery_payload["review_recommendation"]["interval_days"] == 3
    assert "score" not in mastery_payload and "mastered" not in mastery_payload


def test_unassessed_prerequisite_is_gap_not_mastery(tmp_path: Path) -> None:
    workspace, goal_file, diagnostic_file = learning_workspace(tmp_path)
    fixture = json.loads(diagnostic_file.read_text())
    fixture["diagnostic_tasks"] = [
        item for item in fixture["diagnostic_tasks"] if item["concept_id"] != "ordered-comparison"
    ]
    fixture["responses"] = [item for item in fixture["responses"] if item["task_id"] != "diag-a"]
    fixture["exercise_bank"].insert(
        0,
        {
            "id": "exercise-order-1",
            "concept_id": "ordered-comparison",
            "dimension": "recall",
            "prompt": "Choose ascending order.",
            "estimated_minutes": 2,
            "answer": {
                "kind": "single_choice",
                "options": [{"id": "a", "text": "ascending"}],
                "correct_option_id": "a",
            },
        },
    )
    diagnostic_file.write_text(json.dumps(fixture))
    compiled = open_learning_workspace(workspace).start_compile(goal_file, diagnostic_file)
    refs = cast(list[dict[str, Any]], cast(dict[str, Any], compiled["outputs"])["artifacts"])
    artifacts, _ = open_workspace(workspace)
    payload = cast(dict[str, Any], artifacts.get(str(refs[0]["artifact_id"])).artifact.payload)
    states = {
        item["concept_id"]: item["status"] for item in payload["diagnostic"]["concept_states"]
    }
    assert states["ordered-comparison"] == "NOT_ASSESSED"
    assert payload["gaps"][0]["reason"] == "not_assessed"
