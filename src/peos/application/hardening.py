"""Storage-neutral orchestration for release hardening operations."""

from __future__ import annotations

from pathlib import Path

from peos.domain.hardening import WorkspaceInventory
from peos.ports.hardening import HardeningRepository


class HardeningService:
    def __init__(self, repository: HardeningRepository) -> None:
        self._repository = repository

    def inventory(self) -> WorkspaceInventory:
        return self._repository.inventory()

    def create_backup(self, output: Path | None = None, dry_run: bool = False) -> dict[str, object]:
        return self._repository.create_backup(output, dry_run)

    def gc_plan(self) -> dict[str, object]:
        return self._repository.gc_plan()

    def gc_execute(
        self,
        plan_id: str,
        backup: Path,
        *,
        confirmed: bool,
        dry_run: bool = False,
    ) -> dict[str, object]:
        return self._repository.gc_execute(plan_id, backup, confirmed, dry_run)

    def doctor(self) -> dict[str, object]:
        return self._repository.doctor()
