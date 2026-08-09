from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from peos.bootstrap import open_learning_workspace, open_workspace
from peos.ports.fault_injector import SimulatedInterruption, SingleCheckpointFaultInjector
from tests.learning_support import learning_workspace


def test_learning_resume_uses_frozen_inputs(tmp_path: Path) -> None:
    workspace, goal_file, diagnostic_file = learning_workspace(tmp_path)
    service = open_learning_workspace(workspace)
    stopped = service.start_compile(goal_file, diagnostic_file, "freeze-learning-inputs")
    goal_file.unlink()
    diagnostic_file.write_text("changed")
    resumed = service.resume(str(stopped["run_id"]))
    assert resumed["committed_steps"] == 3
    assert service.verify(str(stopped["run_id"]))["valid"] is True


def test_attempt_resume_uses_frozen_attempt_and_does_not_repeat_verification(
    tmp_path: Path,
) -> None:
    workspace, goal_file, diagnostic_file = learning_workspace(tmp_path)
    compiled = open_learning_workspace(workspace).start_compile(goal_file, diagnostic_file)
    refs = cast(list[dict[str, Any]], cast(dict[str, Any], compiled["outputs"])["artifacts"])
    artifacts, _ = open_workspace(workspace)
    goal = artifacts.get(str(refs[0]["artifact_id"]))
    attempt_file = tmp_path / "attempt.json"
    attempt_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "goal_artifact_id": goal.artifact.id,
                "goal_revision": goal.artifact.content_hash,
                "exercise_id": "exercise-interval-1",
                "answer": "low through high",
            }
        )
    )
    interrupted = open_learning_workspace(
        workspace, SingleCheckpointFaultInjector("after_learning_attempt_verified")
    )
    with pytest.raises(SimulatedInterruption):
        interrupted.start_attempt(goal.artifact.id, attempt_file)
    run_id = next(
        path.name
        for path in (workspace / ".peos" / "runs").iterdir()
        if json.loads((path / "manifest.json").read_text())["workflow"]["name"]
        == "learning.record-attempt"
    )
    attempt_file.write_text("changed")
    service = open_learning_workspace(workspace)
    resumed = service.resume(run_id)
    assert resumed["committed_steps"] == 2
    assert service.verify(run_id)["valid"] is True
