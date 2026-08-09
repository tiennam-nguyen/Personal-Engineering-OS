from __future__ import annotations

import json
from pathlib import Path

import pytest

from peos.bootstrap import open_crossflow_workspace
from peos.domain.errors import RunConflictError
from peos.ports.fault_injector import SimulatedInterruption, SingleCheckpointFaultInjector
from tests.crossflow_support import requests, source_workspace


def test_crossflow_resume_frozen_request_and_cancel_idempotently(tmp_path: Path) -> None:
    workspace, claim, charter, packet, goal = source_workspace(tmp_path)
    exercise_request, adr_request, _ = requests(tmp_path, claim, charter, packet, goal)
    service = open_crossflow_workspace(workspace)
    stopped = service.start(exercise_request, "resolve-crossflow-inputs")
    run_id = str(stopped["run_id"])
    step_id = json.loads((workspace / ".peos" / "runs" / run_id / "manifest.json").read_text())[
        "steps"
    ][0]["step_id"]
    events_path = workspace / ".peos" / "runs" / run_id / "events.jsonl"
    before_count = sum(
        f'"step_id":"{step_id}"' in line and '"type":"step.execution_started"' in line
        for line in events_path.read_text().splitlines()
    )
    exercise_request.unlink()
    resumed = service.resume(run_id)
    after_count = sum(
        f'"step_id":"{step_id}"' in line and '"type":"step.execution_started"' in line
        for line in events_path.read_text().splitlines()
    )
    assert resumed["state"] == "SUCCEEDED" and (before_count, after_count) == (1, 1)
    assert service.verify(run_id)["valid"] is True

    cancelled = service.start(adr_request, "resolve-crossflow-inputs")
    cancelled_id = str(cancelled["run_id"])
    cancelled_events = workspace / ".peos" / "runs" / cancelled_id / "events.jsonl"
    first = service.cancel(cancelled_id)
    count = len(cancelled_events.read_text().splitlines())
    second = service.cancel(cancelled_id)
    assert first["state"] == second["state"] == "CANCELLED"
    assert len(cancelled_events.read_text().splitlines()) == count
    assert service.verify(cancelled_id)["valid"] is True
    with pytest.raises(RunConflictError):
        service.resume(cancelled_id)


def test_resume_after_canonical_commit_repairs_projection_without_overwrite(
    tmp_path: Path,
) -> None:
    workspace, claim, charter, packet, goal = source_workspace(tmp_path)
    exercise_request, _, _ = requests(tmp_path, claim, charter, packet, goal)
    interrupted = open_crossflow_workspace(
        workspace,
        SingleCheckpointFaultInjector("after_crossflow_target_canonical_committed"),
    )
    with pytest.raises(SimulatedInterruption):
        interrupted.start(exercise_request)
    run_id = next(
        path.name
        for path in (workspace / ".peos" / "runs").iterdir()
        if json.loads((path / "manifest.json").read_text())["workflow"]["name"]
        == "crossflow.bridge"
    )
    target_id = interrupted.inspect(run_id)["output_artifact_id"]
    target_path = workspace / "artifacts" / "knowledge" / f"{target_id}.md"
    before = target_path.read_bytes()
    resumed = open_crossflow_workspace(workspace).resume(run_id)
    assert resumed["state"] == "SUCCEEDED"
    assert target_path.read_bytes() == before
    assert open_crossflow_workspace(workspace).verify(run_id)["valid"] is True
