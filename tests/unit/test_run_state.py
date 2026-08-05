import pytest

from peos.domain.errors import InvalidRunTransition, TerminalRunError
from peos.domain.runs.model import RunState, StepState
from peos.domain.runs.state import validate_run_transition, validate_step_transition


def test_run_transitions_are_enforced() -> None:
    validate_run_transition(RunState.CREATED, RunState.PLANNED)
    with pytest.raises(InvalidRunTransition):
        validate_run_transition(RunState.CREATED, RunState.SUCCEEDED)
    with pytest.raises(TerminalRunError):
        validate_run_transition(RunState.SUCCEEDED, RunState.RUNNING)


def test_step_transitions_are_enforced() -> None:
    validate_step_transition(StepState.CREATED, StepState.RUNNING)
    with pytest.raises(InvalidRunTransition):
        validate_step_transition(StepState.CREATED, StepState.COMMITTED)
