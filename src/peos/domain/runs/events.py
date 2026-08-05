"""Append-only event hash-chain validation."""

from __future__ import annotations

from datetime import datetime

from peos.domain.errors import JournalCorruptionError
from peos.domain.runs.model import EVENT_ID_PATTERN, RUN_ID_PATTERN, Event, sha256

RUN_EVENTS = {
    "run.created",
    "run.planned",
    "run.started",
    "run.recovering",
    "run.resumed",
    "run.verification_started",
    "run.succeeded",
    "run.failed",
    "run.cancelled",
}
STEP_EVENTS = {
    "step.created",
    "step.inputs_resolved",
    "step.prepared",
    "step.execution_started",
    "step.output_staged",
    "step.verification_started",
    "step.verification_completed",
    "step.committed",
    "step.commit_started",
    "artifact.canonical_committed",
    "artifact.projected",
}
TERMINAL = {"run.succeeded", "run.failed", "run.cancelled"}
PAYLOAD_KEYS = {
    "run.created": {"workflow_name", "workflow_version"},
    "run.planned": {"step_count", "input_manifest_hash"},
    "run.started": set(),
    "run.recovering": {"last_sequence", "frontier"},
    "run.resumed": {"next_step"},
    "run.verification_started": {"committed_steps"},
    "run.succeeded": {"outputs_path", "artifact_count"},
    "run.failed": {"error_code", "failed_step"},
    "run.cancelled": {"frontier", "partial_artifact_count"},
    "step.created": {"ordinal", "name", "version", "side_effect"},
    "step.inputs_resolved": {"input_refs"},
    "step.prepared": {"attempt"},
    "step.execution_started": {"attempt"},
    "step.output_staged": {"evidence_path", "content_hash"},
    "step.verification_started": {"verifier", "version"},
    "step.verification_completed": {"passed", "evidence_path", "content_hash"},
    "step.commit_started": {"output_id"},
    "artifact.canonical_committed": {"artifact_id", "canonical_path", "content_hash"},
    "artifact.projected": {"artifact_id", "content_hash"},
    "step.committed": {"output_refs"},
}


def event_mapping(event: Event, *, include_hash: bool = True) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": event.schema_version,
        "sequence": event.sequence,
        "event_id": event.event_id,
        "occurred_at": event.occurred_at,
        "type": event.type,
        "run_id": event.run_id,
        "step_id": event.step_id,
        "actor": event.actor,
        "payload": event.payload,
        "previous_event_hash": event.previous_event_hash,
    }
    if include_hash:
        value["event_hash"] = event.event_hash
    return value


def verify_events(events: list[Event], step_ids: tuple[str, ...] | None = None) -> None:
    previous: str | None = None
    event_ids: set[str] = set()
    steps: dict[str, set[str]] = {}
    committed_order: list[str] = []
    run_types: list[str] = []
    terminal = False
    run_id: str | None = None
    for expected, event in enumerate(events, 1):
        if event.schema_version != 1 or event.actor != {"kind": "system", "id": "peos"}:
            raise JournalCorruptionError("Journal schema version or actor is invalid.")
        if terminal:
            raise JournalCorruptionError("Journal contains an event after terminal state.")
        if event.sequence != expected or not EVENT_ID_PATTERN.fullmatch(event.event_id):
            raise JournalCorruptionError("Journal event sequence or ID is invalid.")
        if event.event_id in event_ids:
            raise JournalCorruptionError("Journal event IDs must be unique.")
        event_ids.add(event.event_id)
        if not RUN_ID_PATTERN.fullmatch(event.run_id):
            raise JournalCorruptionError("Journal run ID is invalid.")
        if run_id is None:
            run_id = event.run_id
        elif event.run_id != run_id:
            raise JournalCorruptionError("Journal contains a foreign run ID.")
        try:
            timestamp = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        except ValueError as error:
            raise JournalCorruptionError("Journal timestamp is invalid.") from error
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise JournalCorruptionError("Journal timestamp must be timezone-aware.")
        if event.type not in RUN_EVENTS | STEP_EVENTS:
            raise JournalCorruptionError("Journal event type is not registered.")
        if set(event.payload) != PAYLOAD_KEYS[event.type]:
            raise JournalCorruptionError("Journal event payload fields are invalid.")
        if event.type in RUN_EVENTS and event.step_id is not None:
            raise JournalCorruptionError("Run event cannot reference a step.")
        if event.type in STEP_EVENTS and event.step_id is None:
            raise JournalCorruptionError("Step event must reference a step.")
        if step_ids is not None and event.step_id is not None and event.step_id not in step_ids:
            raise JournalCorruptionError("Journal event references an unknown manifest step.")
        evidence = event.payload.get("evidence_path")
        if evidence is not None:
            if not isinstance(evidence, str):
                raise JournalCorruptionError("Evidence path must be a string.")
            normalized = evidence.replace("\\", "/")
            parts = tuple(part for part in normalized.split("/") if part)
            if normalized.startswith("/") or ".." in parts or not parts or parts[0] != "evidence":
                raise JournalCorruptionError("Evidence path escapes the run directory.")
        if event.previous_event_hash != previous:
            raise JournalCorruptionError("Journal previous-event hash chain is invalid.")
        if event.event_hash != sha256(event_mapping(event, include_hash=False)):
            raise JournalCorruptionError("Journal event content hash is invalid.")
        previous = event.event_hash
        if (
            step_ids is not None
            and len(step_ids) == 2
            and event.type == "step.created"
            and event.step_id == step_ids[1]
            and step_ids[0] not in committed_order
        ):
            raise JournalCorruptionError("Step 2 cannot start before step 1 commits.")
        _replay_event(event, steps, committed_order, run_types)
        terminal = event.type in TERMINAL


def _replay_event(
    event: Event, steps: dict[str, set[str]], committed: list[str], run_types: list[str]
) -> None:
    if event.type == "run.created" and event.sequence != 1:
        raise JournalCorruptionError("run.created must be the first event.")
    if event.type == "run.planned" and event.sequence != 2:
        raise JournalCorruptionError("run.planned must follow run.created.")
    if event.type == "run.started" and event.sequence != 3:
        raise JournalCorruptionError("run.started must follow run.planned.")
    if event.step_id is None:
        if event.type in {"run.verification_started", "run.succeeded"} and len(committed) != 2:
            raise JournalCorruptionError("Run cannot verify or succeed before both steps commit.")
        if event.type == "run.succeeded" and "run.verification_started" not in run_types:
            raise JournalCorruptionError("Run cannot succeed before verification.")
        run_types.append(event.type)
        return
    seen = steps.setdefault(event.step_id, set())
    if "step.committed" in seen:
        raise JournalCorruptionError("Committed step cannot transition.")
    requirements = {
        "step.inputs_resolved": "step.created",
        "step.prepared": "step.inputs_resolved",
        "step.execution_started": "step.prepared",
        "step.output_staged": "step.execution_started",
        "step.verification_started": "step.output_staged",
        "step.verification_completed": "step.verification_started",
        "step.commit_started": "step.output_staged",
        "artifact.canonical_committed": "step.commit_started",
        "artifact.projected": "artifact.canonical_committed",
        "step.committed": "step.verification_completed",
    }
    required = requirements.get(event.type)
    if required is not None and required not in seen:
        raise JournalCorruptionError("Illegal step lifecycle transition.")
    if event.type in seen:
        raise JournalCorruptionError("Duplicate durable step transition.")
    if event.type == "artifact.projected" and "artifact.canonical_committed" not in seen:
        raise JournalCorruptionError("Projection cannot precede canonical commit.")
    seen.add(event.type)
    if event.type == "step.committed":
        committed.append(event.step_id)
