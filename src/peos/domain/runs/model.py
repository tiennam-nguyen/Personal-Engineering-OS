"""Immutable values used by the deterministic run journal."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

RUN_ID_PATTERN = re.compile(r"^run_[0-9a-f]{32}$")
STEP_ID_PATTERN = re.compile(r"^step_[0-9a-f]{32}$")
EVENT_ID_PATTERN = re.compile(r"^evt_[0-9a-f]{32}$")


class RunState(StrEnum):
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    WAITING_INPUT = "WAITING_INPUT"
    PAUSED_BUDGET = "PAUSED_BUDGET"
    RECOVERING = "RECOVERING"
    VERIFYING = "VERIFYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepState(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    VERIFIED = "VERIFIED"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class Event:
    schema_version: int
    event_id: str
    run_id: str
    step_id: str | None
    sequence: int
    occurred_at: str
    type: str
    actor: dict[str, str]
    payload: dict[str, object]
    previous_event_hash: str | None
    event_hash: str

    @property
    def content_hash(self) -> str:
        return self.event_hash

    @property
    def timestamp(self) -> str:
        return self.occurred_at


def canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def sha256(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def deterministic_step_id(run_id: str, ordinal: int, name: str, version: str) -> str:
    source = f"{run_id}:{ordinal}:{name}:{version}".encode()
    return "step_" + hashlib.sha256(source).hexdigest()[:32]
