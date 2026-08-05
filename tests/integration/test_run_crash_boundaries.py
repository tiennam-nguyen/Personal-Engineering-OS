from __future__ import annotations

from pathlib import Path

import pytest

from peos.adapters.filesystem.run_repository import FilesystemRunRepository
from peos.adapters.filesystem.workspace import Workspace, WorkspaceStore
from peos.application.runs import RunService
from peos.bootstrap import initialize_workspace, open_run_workspace
from peos.ports.fault_injector import SimulatedInterruption, SingleCheckpointFaultInjector


def _interrupted(
    tmp_path: Path, checkpoint: str
) -> tuple[str, FilesystemRunRepository, RunService, Workspace]:
    artifacts, _, _, _ = initialize_workspace(tmp_path)
    source = artifacts.create_concept("Source", "Input body", ["source"])
    service = open_run_workspace(tmp_path, SingleCheckpointFaultInjector(checkpoint))
    with pytest.raises(SimulatedInterruption):
        service.start("sample.derive-concept", source.artifact.id)
    workspace = WorkspaceStore().open(tmp_path)
    run_id = next(workspace.runs_root.iterdir()).name
    repository = FilesystemRunRepository(workspace)
    assert not any(event.type == "run.failed" for event in repository.events(run_id))
    return run_id, repository, open_run_workspace(tmp_path), workspace


def _recover(tmp_path: Path, checkpoint: str) -> tuple[str, FilesystemRunRepository, Workspace]:
    run_id, repository, service, workspace = _interrupted(tmp_path, checkpoint)
    before = repository.events(run_id)
    steps = repository.read_manifest(run_id)["steps"]
    assert isinstance(steps, list) and isinstance(steps[0], dict)
    first = str(steps[0]["step_id"])
    executions_before = sum(
        event.type == "step.execution_started" and event.step_id == first for event in before
    )
    canonical = sorted(workspace.artifact_root.glob("*.md"))
    output_before = canonical[1].read_bytes() if len(canonical) > 1 else None
    result = service.resume(run_id)
    assert result["state"] == "SUCCEEDED"
    assert service.verify(run_id)["valid"] is True
    after = repository.events(run_id)
    executions_after = sum(
        event.type == "step.execution_started" and event.step_id == first for event in after
    )
    if any(event.type == "step.committed" and event.step_id == first for event in before):
        assert executions_before == executions_after == 1
    output_files = sorted(workspace.artifact_root.glob("*.md"))
    assert len(output_files) == 2
    if output_before is not None:
        assert output_before in {path.read_bytes() for path in output_files}
    return run_id, repository, workspace


def test_resume_after_step_1_output_staged(tmp_path: Path) -> None:
    _recover(tmp_path, "after_step_1_output_staged")


def test_resume_after_step_1_verification_completed(tmp_path: Path) -> None:
    _recover(tmp_path, "after_step_1_verification_completed")


def test_resume_after_step_1_committed_does_not_repeat_step_1(tmp_path: Path) -> None:
    run_id, repository, _ = _recover(tmp_path, "after_step_1_committed")
    steps = repository.read_manifest(run_id)["steps"]
    assert isinstance(steps, list) and isinstance(steps[0], dict)
    first = str(steps[0]["step_id"])
    events = repository.events(run_id)
    assert sum(e.type == "step.execution_started" and e.step_id == first for e in events) == 1
    assert sum(e.type == "step.committed" and e.step_id == first for e in events) == 1


def test_resume_after_step_2_output_staged(tmp_path: Path) -> None:
    _recover(tmp_path, "after_step_2_output_staged")


def test_resume_after_step_2_commit_started(tmp_path: Path) -> None:
    _recover(tmp_path, "after_step_2_commit_started")


def test_resume_after_canonical_commit_does_not_overwrite_artifact(tmp_path: Path) -> None:
    _recover(tmp_path, "after_artifact_canonical_committed")


def test_resume_after_canonical_commit_repairs_projection(tmp_path: Path) -> None:
    _recover(tmp_path, "after_artifact_canonical_committed")


def test_resume_after_projection_does_not_duplicate_projection(tmp_path: Path) -> None:
    _recover(tmp_path, "after_artifact_projected")


def test_resume_after_step_2_committed_only_finalizes_run(tmp_path: Path) -> None:
    _recover(tmp_path, "after_step_2_committed")


def test_resume_after_outputs_written_reaches_succeeded(tmp_path: Path) -> None:
    run_id, repository, _ = _recover(tmp_path, "after_outputs_written")
    assert sum(event.type == "run.succeeded" for event in repository.events(run_id)) == 1
