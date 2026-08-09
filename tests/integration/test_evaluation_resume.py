from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from peos.adapters.filesystem.run_repository import FilesystemRunRepository
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.bootstrap import open_evaluation_workspace
from peos.domain.errors import ModelCallOutcomeUnknown, TerminalRunError
from peos.domain.runs.model import Event
from peos.ports.fault_injector import SimulatedInterruption, SingleCheckpointFaultInjector

from .test_evaluation_workflow import workspace


def _run_id(root: Path) -> str:
    return next(WorkspaceStore().open(root).runs_root.iterdir()).name


def _events(root: Path, run_id: str) -> list[Event]:
    return FilesystemRunRepository(WorkspaceStore().open(root)).events(run_id)


def _interrupt(root: Path, checkpoint: str) -> str:
    service = open_evaluation_workspace(root, SingleCheckpointFaultInjector(checkpoint))
    with pytest.raises(SimulatedInterruption):
        service.start("model.summarization.core", "mock", "deterministic-concept-summary-v1", "1")
    return _run_id(root)


def test_resume_uses_frozen_suite_after_source_files_are_removed(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    stopped = open_evaluation_workspace(root).start(
        "model.summarization.core",
        "mock",
        "deterministic-concept-summary-v1",
        "1",
        "freeze-eval-suite",
    )
    run_id = str(stopped["run_id"])
    shutil.rmtree(root / "evals")

    assert open_evaluation_workspace(root).resume(run_id)["state"] == "SUCCEEDED"
    assert open_evaluation_workspace(root).verify(run_id)["valid"] is True


def test_resume_does_not_repeat_audited_case(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    run_id = _interrupt(root, "after_eval_case_1_audited")
    before = _events(root, run_id)
    first_call_id = next(
        event.payload["call_id"]
        for event in before
        if getattr(event, "type") == "model.call_started"
    )

    assert open_evaluation_workspace(root).resume(run_id)["state"] == "SUCCEEDED"
    after = _events(root, run_id)
    assert (
        sum(
            event.type == "model.call_started" and event.payload.get("call_id") == first_call_id
            for event in after
        )
        == 1
    )
    assert sum(event.type == "model.call_started" for event in after) == 3


def test_resume_after_all_cases_executed_only_scores(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    stopped = open_evaluation_workspace(root).start(
        "model.summarization.core",
        "mock",
        "deterministic-concept-summary-v1",
        "1",
        "execute-eval-cases",
    )
    run_id = str(stopped["run_id"])
    assert sum(event.type == "model.call_started" for event in _events(root, run_id)) == 3

    assert open_evaluation_workspace(root).resume(run_id)["state"] == "SUCCEEDED"
    assert sum(event.type == "model.call_started" for event in _events(root, run_id)) == 3


def test_resume_refuses_unknown_candidate_call_outcome(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    run_id = _interrupt(root, "after_eval_case_1_call_started")

    with pytest.raises(ModelCallOutcomeUnknown):
        open_evaluation_workspace(root).resume(run_id)
    assert sum(event.type == "model.call_started" for event in _events(root, run_id)) == 1


@pytest.mark.parametrize(
    "checkpoint",
    [
        "after_eval_report_canonical_commit",
        "after_eval_outputs_written",
    ],
)
def test_resume_across_final_commit_boundaries(tmp_path: Path, checkpoint: str) -> None:
    root = workspace(tmp_path)
    run_id = _interrupt(root, checkpoint)
    canonical_before = sorted((root / "artifacts").glob("*.md"))
    payloads_before = {path: path.read_bytes() for path in canonical_before}

    assert open_evaluation_workspace(root).resume(run_id)["state"] == "SUCCEEDED"
    assert {path: path.read_bytes() for path in canonical_before} == payloads_before
    assert open_evaluation_workspace(root).verify(run_id)["valid"] is True


def test_cancel_is_idempotent_and_blocks_resume(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    stopped = open_evaluation_workspace(root).start(
        "model.summarization.core",
        "mock",
        "deterministic-concept-summary-v1",
        "1",
        "freeze-eval-suite",
    )
    run_id = str(stopped["run_id"])
    service = open_evaluation_workspace(root)
    assert service.cancel(run_id)["state"] == "CANCELLED"
    count = len(_events(root, run_id))
    assert service.cancel(run_id)["state"] == "CANCELLED"
    assert len(_events(root, run_id)) == count
    with pytest.raises(TerminalRunError):
        service.resume(run_id)
