"""Run and step transition validation."""

from __future__ import annotations

from peos.domain.errors import InvalidRunTransition, TerminalRunError
from peos.domain.runs.model import RunState, StepState

_RUN = {
    RunState.CREATED: {RunState.PLANNED, RunState.FAILED, RunState.CANCELLED},
    RunState.PLANNED: {RunState.RUNNING, RunState.FAILED, RunState.CANCELLED},
    RunState.RUNNING: {
        RunState.RECOVERING,
        RunState.VERIFYING,
        RunState.FAILED,
        RunState.CANCELLED,
    },
    RunState.RECOVERING: {
        RunState.RUNNING,
        RunState.VERIFYING,
        RunState.FAILED,
        RunState.CANCELLED,
    },
    RunState.VERIFYING: {RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED},
}
_STEP = {
    StepState.CREATED: {StepState.RUNNING, StepState.FAILED},
    StepState.RUNNING: {StepState.VERIFIED, StepState.FAILED},
    StepState.VERIFIED: {StepState.COMMITTED, StepState.FAILED},
}


def validate_run_transition(before: RunState, after: RunState) -> None:
    if before in {RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED}:
        raise TerminalRunError("Terminal runs cannot transition.")
    if after not in _RUN.get(before, set()):
        raise InvalidRunTransition(f"Invalid run transition {before} -> {after}.")


def validate_step_transition(before: StepState, after: StepState) -> None:
    if after not in _STEP.get(before, set()):
        raise InvalidRunTransition(f"Invalid step transition {before} -> {after}.")
