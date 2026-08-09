from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from peos.bootstrap import open_learning_workspace, open_workspace
from peos.domain.errors import RunConflictError
from peos.ports.fault_injector import SimulatedInterruption, SingleCheckpointFaultInjector
from tests.learning_support import learning_workspace


def test_learning_cancel_is_idempotent_and_verifies(tmp_path: Path) -> None:
    workspace, goal_file, diagnostic_file = learning_workspace(tmp_path)
    service = open_learning_workspace(workspace)
    stopped = service.start_compile(goal_file, diagnostic_file, "freeze-learning-inputs")
    run_id = str(stopped["run_id"])
    assert service.cancel(run_id)["state"] == "CANCELLED"
    assert service.cancel(run_id)["state"] == "CANCELLED"
    assert service.verify(run_id)["valid"] is True
    with pytest.raises(RunConflictError):
        service.resume(run_id)


def test_learning_attempt_cancellation_preserves_goal(tmp_path: Path) -> None:
    workspace, goal_file, diagnostic_file = learning_workspace(tmp_path)
    compiled = open_learning_workspace(workspace).start_compile(goal_file, diagnostic_file)
    refs = cast(list[dict[str, Any]], cast(dict[str, Any], compiled["outputs"])["artifacts"])
    artifacts, _ = open_workspace(workspace)
    goal = artifacts.get(str(refs[0]["artifact_id"]))
    revision = goal.artifact.content_hash
    attempt_file = tmp_path / "attempt.json"
    attempt_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "goal_artifact_id": goal.artifact.id,
                "goal_revision": revision,
                "exercise_id": "exercise-interval-1",
                "answer": "low through high",
            }
        )
    )
    service = open_learning_workspace(
        workspace, SingleCheckpointFaultInjector("after_learning_attempt_verified")
    )
    with pytest.raises(SimulatedInterruption):
        service.start_attempt(goal.artifact.id, attempt_file)
    run_id = next(
        path.name
        for path in (workspace / ".peos" / "runs").iterdir()
        if json.loads((path / "manifest.json").read_text())["workflow"]["name"]
        == "learning.record-attempt"
    )
    assert open_learning_workspace(workspace).cancel(run_id)["state"] == "CANCELLED"
    assert artifacts.get(goal.artifact.id).artifact.content_hash == revision
