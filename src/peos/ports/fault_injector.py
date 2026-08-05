"""Storage-neutral recovery fault injection seam."""

from __future__ import annotations

from typing import Protocol


class FaultInjector(Protocol):
    def checkpoint(self, name: str) -> None: ...


class NoOpFaultInjector:
    def checkpoint(self, name: str) -> None:
        del name


class SimulatedInterruption(Exception):
    """Test-only interruption which intentionally leaves durable state active."""


class SingleCheckpointFaultInjector:
    def __init__(self, checkpoint: str) -> None:
        self._checkpoint = checkpoint
        self._fired = False

    def checkpoint(self, name: str) -> None:
        if name == self._checkpoint and not self._fired:
            self._fired = True
            raise SimulatedInterruption(name)
