from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from peos.adapters.filesystem.run_repository import FilesystemRunRepository
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.domain.errors import JournalCorruptionError, RunConflictError
from peos.domain.runs.events import event_mapping, verify_events
from peos.domain.runs.model import Event, sha256

RUN_ID = "run_" + "b" * 32
STEP_1 = "step_" + "1" * 32
STEP_2 = "step_" + "2" * 32


def _add(
    events: list[Event],
    type_: str,
    step_id: str | None = None,
    payload: dict[str, object] | None = None,
) -> Event:
    raw = Event(
        1,
        "evt_" + uuid.uuid4().hex,
        RUN_ID,
        step_id,
        len(events) + 1,
        "2026-01-01T00:00:00Z",
        type_,
        {"kind": "system", "id": "peos"},
        payload or {},
        events[-1].content_hash if events else None,
        "",
    )
    event = Event(**{**raw.__dict__, "event_hash": sha256(event_mapping(raw, include_hash=False))})
    events.append(event)
    return event


def _base() -> list[Event]:
    events: list[Event] = []
    _add(
        events,
        "run.created",
        payload={"workflow_name": "sample.derive-concept", "workflow_version": "1.0.0"},
    )
    _add(
        events,
        "run.planned",
        payload={"step_count": 2, "input_manifest_hash": "sha256:" + "a" * 64},
    )
    _add(events, "run.started")
    return events


def _commit(events: list[Event], step_id: str, ordinal: int) -> None:
    _add(
        events,
        "step.created",
        step_id,
        {"ordinal": ordinal, "name": "step", "version": "1.0.0", "side_effect": "PURE"},
    )
    _add(events, "step.inputs_resolved", step_id, {"input_refs": []})
    _add(events, "step.prepared", step_id, {"attempt": 1})
    _add(events, "step.execution_started", step_id, {"attempt": 1})
    _add(
        events,
        "step.output_staged",
        step_id,
        {"evidence_path": "evidence/output.json", "content_hash": "sha256:" + "a" * 64},
    )
    _add(events, "step.verification_started", step_id, {"verifier": "verify", "version": "1.0.0"})
    _add(
        events,
        "step.verification_completed",
        step_id,
        {
            "passed": True,
            "evidence_path": "evidence/verify.json",
            "content_hash": "sha256:" + "b" * 64,
        },
    )
    _add(events, "step.committed", step_id, {"output_refs": []})


def test_invalid_event_type_is_rejected() -> None:
    events = _base()
    _add(events, "unknown.event")
    with pytest.raises(JournalCorruptionError):
        verify_events(events)


def test_unknown_step_id_is_rejected() -> None:
    events = _base()
    _add(events, "step.created", "step_" + "f" * 32)
    with pytest.raises(JournalCorruptionError):
        verify_events(events, (STEP_1, STEP_2))


def test_illegal_step_transition_is_rejected() -> None:
    events = _base()
    _add(events, "step.committed", STEP_1)
    with pytest.raises(JournalCorruptionError):
        verify_events(events, (STEP_1, STEP_2))


def test_step_2_cannot_start_before_step_1_commit() -> None:
    events = _base()
    _add(events, "step.created", STEP_2)
    with pytest.raises(JournalCorruptionError):
        verify_events(events, (STEP_1, STEP_2))


def test_projection_event_cannot_precede_canonical_commit() -> None:
    events = _base()
    _commit(events, STEP_1, 1)
    _add(events, "step.created", STEP_2, {"ordinal": 2})
    _add(events, "step.execution_started", STEP_2, {"attempt": 1})
    _add(events, "step.output_staged", STEP_2, {"evidence": "evidence/output.json"})
    _add(events, "artifact.projected", STEP_2)
    with pytest.raises(JournalCorruptionError):
        verify_events(events, (STEP_1, STEP_2))


def test_succeeded_before_both_steps_commit_is_rejected() -> None:
    events = _base()
    _add(events, "run.verification_started", payload={"committed_steps": 2})
    with pytest.raises(JournalCorruptionError):
        verify_events(events, (STEP_1, STEP_2))


def test_event_after_terminal_state_is_rejected() -> None:
    events = _base()
    _add(events, "run.cancelled", payload={"frontier": "running", "partial_artifact_count": 0})
    _add(events, "run.started")
    with pytest.raises(JournalCorruptionError):
        verify_events(events)


def _repository(tmp_path: Path) -> tuple[FilesystemRunRepository, Path]:
    workspace, _ = WorkspaceStore().initialize(tmp_path)
    repository = FilesystemRunRepository(workspace)
    repository.create(
        {"run_id": RUN_ID, "steps": [{"step_id": STEP_1}, {"step_id": STEP_2}]},
        {},
    )
    return repository, workspace.runs_root / RUN_ID / "events.jsonl"


@pytest.mark.parametrize("content", ["not-json\n", '{"sequence":1\n'])
def test_malformed_json_line_is_rejected(tmp_path: Path, content: str) -> None:
    repository, path = _repository(tmp_path)
    path.write_text(content, encoding="utf-8")
    with pytest.raises(JournalCorruptionError):
        repository.events(RUN_ID)


def test_partial_json_line_is_rejected(tmp_path: Path) -> None:
    test_malformed_json_line_is_rejected(tmp_path, '{"sequence":1')


def test_blank_json_line_is_rejected(tmp_path: Path) -> None:
    repository, path = _repository(tmp_path)
    path.write_text("\n", encoding="utf-8")
    with pytest.raises(JournalCorruptionError):
        repository.events(RUN_ID)


def test_missing_final_newline_is_rejected(tmp_path: Path) -> None:
    repository, path = _repository(tmp_path)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(JournalCorruptionError):
        repository.events(RUN_ID)


def test_duplicate_event_id_is_rejected() -> None:
    events = _base()
    duplicate = Event(
        **{**events[-1].__dict__, "sequence": 4, "previous_event_hash": events[-1].content_hash}
    )
    duplicate = Event(
        **{
            **duplicate.__dict__,
            "event_hash": sha256(event_mapping(duplicate, include_hash=False)),
        }
    )
    with pytest.raises(JournalCorruptionError):
        verify_events(events + [duplicate])


def test_sequence_gap_is_rejected() -> None:
    events = _base()
    with pytest.raises(JournalCorruptionError):
        verify_events([Event(**{**events[0].__dict__, "sequence": 2})])


def test_previous_event_hash_mismatch_is_rejected() -> None:
    events = _base()
    with pytest.raises(JournalCorruptionError):
        verify_events(
            [
                events[0],
                Event(**{**events[1].__dict__, "previous_event_hash": "sha256:" + "0" * 64}),
            ]
        )


def test_event_payload_tampering_is_detected() -> None:
    events = _base()
    with pytest.raises(JournalCorruptionError):
        verify_events([Event(**{**events[0].__dict__, "payload": {"tampered": True}})])


def test_evidence_path_escape_is_rejected() -> None:
    events = _base()
    _add(events, "step.created", STEP_1)
    _add(events, "step.inputs_resolved", STEP_1)
    _add(events, "step.prepared", STEP_1)
    _add(events, "step.execution_started", STEP_1)
    _add(events, "step.output_staged", STEP_1, {"evidence_path": "../secret"})
    with pytest.raises(JournalCorruptionError):
        verify_events(events, (STEP_1, STEP_2))


def test_conflicting_outputs_manifest_is_rejected(tmp_path: Path) -> None:
    repository, _ = _repository(tmp_path)
    repository.write_outputs(RUN_ID, {"status": "SUCCEEDED"})
    with pytest.raises(RunConflictError):
        repository.write_outputs(RUN_ID, {"status": "CANCELLED"})
