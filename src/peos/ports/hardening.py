"""Port for canonical inventory and release-hardening storage operations."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from peos.domain.hardening import WorkspaceInventory


class HardeningRepository(Protocol):
    def inventory(self) -> WorkspaceInventory: ...

    def create_backup(self, output: Path | None, dry_run: bool) -> dict[str, object]: ...

    def gc_plan(self) -> dict[str, object]: ...

    def gc_execute(
        self, plan_id: str, backup: Path, confirmed: bool, dry_run: bool
    ) -> dict[str, object]: ...

    def doctor(self) -> dict[str, object]: ...
