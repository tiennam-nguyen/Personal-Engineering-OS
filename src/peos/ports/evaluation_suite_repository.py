"""Port for canonical evaluation suite assets."""

from __future__ import annotations

from typing import Protocol

from peos.domain.evaluations import EvalSuite


class EvaluationSuiteRepository(Protocol):
    def active_for_task(self, task_kind: str) -> EvalSuite: ...

    def get(self, name: str) -> EvalSuite: ...

    def list_active(self) -> tuple[EvalSuite, ...]: ...
