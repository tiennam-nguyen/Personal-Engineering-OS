"""Trusted typed migration registry and generation-gated migration orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class MigrationDefinition:
    id: str
    version: str
    kind: str
    side_effect: str
    description: str
    current_schema_version: int
    target_schema_version: int
    requires_backup: bool


class MigrationRepository(Protocol):
    def status(self) -> dict[str, object]: ...

    def plan(self) -> dict[str, object]: ...

    def apply(
        self, plan_id: str, backup: Path | None, confirmed: bool, dry_run: bool
    ) -> dict[str, object]: ...


class MigrationService:
    def __init__(self, repository: MigrationRepository) -> None:
        self._repository = repository

    def status(self) -> dict[str, object]:
        return self._repository.status()

    def plan(self) -> dict[str, object]:
        return self._repository.plan()

    def apply(
        self,
        plan_id: str,
        backup: Path | None,
        *,
        confirmed: bool,
        dry_run: bool,
    ) -> dict[str, object]:
        return self._repository.apply(plan_id, backup, confirmed, dry_run)
