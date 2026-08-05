from __future__ import annotations

from pathlib import Path

import pytest

from peos.adapters.filesystem.run_repository import FilesystemRunRepository
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.application.runs import RunService
from peos.bootstrap import initialize_workspace, open_run_workspace
from peos.domain.errors import RunConflictError, TerminalRunError
from peos.ports.fault_injector import SimulatedInterruption, SingleCheckpointFaultInjector


def _stopped(tmp_path: Path) -> tuple[str, RunService, FilesystemRunRepository]:
    artifacts, _, _, _ = initialize_workspace(tmp_path)
    source = artifacts.create_concept("Source", "Body", [])
    service = open_run_workspace(tmp_path)
    view = service.start("sample.derive-concept", source.artifact.id, "prepare-derived-concept")
    run_id = str(view["run_id"])
    repository = FilesystemRunRepository(WorkspaceStore().open(tmp_path))
    return run_id, service, repository


def test_active_stopped_run_can_be_cancelled(tmp_path: Path) -> None:
    run_id, service, _ = _stopped(tmp_path)
    assert service.cancel(run_id)["state"] == "CANCELLED"


def test_cancelled_run_cannot_resume(tmp_path: Path) -> None:
    run_id, service, _ = _stopped(tmp_path)
    service.cancel(run_id)
    with pytest.raises(RunConflictError):
        service.resume(run_id)


def test_cancelled_run_is_terminal(tmp_path: Path) -> None:
    run_id, service, repository = _stopped(tmp_path)
    service.cancel(run_id)
    with pytest.raises(RunConflictError):
        service._event(run_id, "run.started", None, {})
    assert repository.events(run_id)[-1].type == "run.cancelled"


def test_repeated_cancel_is_idempotent_without_new_event(tmp_path: Path) -> None:
    run_id, service, repository = _stopped(tmp_path)
    service.cancel(run_id)
    count = len(repository.events(run_id))
    service.cancel(run_id)
    assert len(repository.events(run_id)) == count


def test_succeeded_run_cannot_be_cancelled(tmp_path: Path) -> None:
    artifacts, _, _, _ = initialize_workspace(tmp_path)
    source = artifacts.create_concept("Source", "Body", [])
    service = open_run_workspace(tmp_path)
    run_id = str(service.start("sample.derive-concept", source.artifact.id)["run_id"])
    with pytest.raises(TerminalRunError):
        service.cancel(run_id)


def test_failed_run_cannot_be_cancelled(tmp_path: Path) -> None:
    run_id, service, _ = _stopped(tmp_path)
    service._event(run_id, "run.failed", None, {"error_code": "test", "failed_step": None})
    with pytest.raises(TerminalRunError):
        service.cancel(run_id)


def test_cancel_preserves_existing_evidence(tmp_path: Path) -> None:
    run_id, service, repository = _stopped(tmp_path)
    before = repository.read_evidence(run_id, "step-01-prepared-artifact.json")
    service.cancel(run_id)
    assert repository.read_evidence(run_id, "step-01-prepared-artifact.json") == before


def test_cancel_does_not_delete_partial_canonical_artifact(tmp_path: Path) -> None:
    artifacts, _, _, _ = initialize_workspace(tmp_path)
    source = artifacts.create_concept("Source", "Body", [])
    interrupted = open_run_workspace(
        tmp_path, SingleCheckpointFaultInjector("after_artifact_canonical_committed")
    )
    with pytest.raises(SimulatedInterruption):
        interrupted.start("sample.derive-concept", source.artifact.id)
    workspace = WorkspaceStore().open(tmp_path)
    run_id = next(workspace.runs_root.iterdir()).name
    canonical = sorted(workspace.artifact_root.glob("*.md"))[1]
    before = canonical.read_bytes()
    open_run_workspace(tmp_path).cancel(run_id)
    assert canonical.read_bytes() == before


def test_cancelled_run_verify_passes(tmp_path: Path) -> None:
    run_id, service, _ = _stopped(tmp_path)
    service.cancel(run_id)
    assert service.verify(run_id) == {"run_id": run_id, "valid": True, "state": "CANCELLED"}


def test_no_event_can_be_appended_after_terminal_state(tmp_path: Path) -> None:
    run_id, service, repository = _stopped(tmp_path)
    service.cancel(run_id)
    terminal = repository.events(run_id)[-1]
    with pytest.raises(RunConflictError):
        repository.append(run_id, terminal)
