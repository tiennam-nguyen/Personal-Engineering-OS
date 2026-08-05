"""Workflow metadata values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StepDefinition:
    ordinal: int
    name: str
    version: str
    side_effect: str
    max_attempts: int = 1
    max_output_bytes: int = 65536


@dataclass(frozen=True)
class WorkflowDefinition:
    name: str
    version: str
    steps: tuple[StepDefinition, ...]
