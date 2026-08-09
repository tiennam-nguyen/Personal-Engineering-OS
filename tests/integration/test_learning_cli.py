from __future__ import annotations

import json
from pathlib import Path

import pytest

from peos.cli.main import main
from tests.learning_support import learning_workspace


def test_learning_cli_compile_attempt_and_verify(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace, goal_file, diagnostic_file = learning_workspace(tmp_path)
    assert (
        main(
            [
                "--workspace",
                str(workspace),
                "learn",
                "compile",
                "--goal-file",
                str(goal_file),
                "--diagnostic-file",
                str(diagnostic_file),
            ]
        )
        == 0
    )
    compiled = json.loads(capsys.readouterr().out)
    goal_ref = compiled["outputs"]["artifacts"][0]
    attempt = tmp_path / "attempt.json"
    attempt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "goal_artifact_id": goal_ref["artifact_id"],
                "goal_revision": goal_ref["content_hash"],
                "exercise_id": "exercise-interval-1",
                "answer": "low through high",
            }
        )
    )
    assert (
        main(
            [
                "--workspace",
                str(workspace),
                "learn",
                "attempt",
                "--goal",
                goal_ref["artifact_id"],
                "--attempt-file",
                str(attempt),
            ]
        )
        == 0
    )
    attempted = json.loads(capsys.readouterr().out)
    assert main(["--workspace", str(workspace), "run", "verify", attempted["run_id"]]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
