"""Filesystem records and disposable-index migration implementation."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import cast

from peos.adapters.filesystem.hardening import (
    APPLICATION_VERSION,
    FilesystemHardeningRepository,
    _json,
    _now,
    _write_new,
    verify_backup,
)
from peos.adapters.filesystem.repository import FilesystemArtifactRepository
from peos.adapters.filesystem.workspace import Workspace, WorkspaceStore
from peos.adapters.sqlite.artifact_index import CURRENT_SCHEMA_VERSION, SQLiteArtifactIndex
from peos.application.indexing import IndexingService
from peos.application.migrations import MigrationDefinition
from peos.domain.errors import MigrationBlockedError
from peos.domain.runs.model import sha256

LEGACY_INDEX = MigrationDefinition(
    "index.legacy-to-current",
    "1.0.0",
    "index",
    "DERIVED_REBUILD",
    "Rebuild a legacy or missing disposable SQLite projection from canonical artifacts.",
    0,
    CURRENT_SCHEMA_VERSION,
    False,
)


class FilesystemMigrationRepository:
    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def status(self) -> dict[str, object]:
        current = SQLiteArtifactIndex(self._workspace.index_path).schema_version()
        return {
            "workspace_id": self._workspace.workspace_id,
            "current_index_schema_version": current,
            "target_index_schema_version": CURRENT_SCHEMA_VERSION,
            "status": "current" if current == CURRENT_SCHEMA_VERSION else "migration_available",
            "available_migrations": [] if current == CURRENT_SCHEMA_VERSION else [LEGACY_INDEX.id],
        }

    def plan(self) -> dict[str, object]:
        status = self.status()
        if status["status"] == "current":
            return {**status, "plan_id": None, "already_current": True}
        inventory = FilesystemHardeningRepository(self._workspace).inventory()
        plan_id = "migplan_" + uuid.uuid4().hex
        content = {
            "schema_version": 1,
            "plan_id": plan_id,
            "migration_id": LEGACY_INDEX.id,
            "migration_version": LEGACY_INDEX.version,
            "kind": LEGACY_INDEX.kind,
            "workspace_id": inventory.workspace_id,
            "workspace_generation": inventory.generation,
            "current_schema_version": status["current_index_schema_version"],
            "target_schema_version": CURRENT_SCHEMA_VERSION,
            "side_effect": LEGACY_INDEX.side_effect,
            "planned_changes": "rebuild derived SQLite projection from canonical artifacts",
            "requires_backup": False,
            "created_at": _now(),
        }
        sealed = {**content, "plan_hash": sha256(content)}
        path = self._plans / f"{plan_id}.json"
        _write_new(path, json.dumps(sealed, sort_keys=True, indent=2).encode() + b"\n")
        return sealed

    def apply(
        self, plan_id: str, backup: Path | None, confirmed: bool, dry_run: bool
    ) -> dict[str, object]:
        if not confirmed:
            raise MigrationBlockedError("Migration apply requires explicit confirmation.")
        record_path = self._records / f"{plan_id}.json"
        if record_path.exists():
            record = _json(record_path.read_bytes(), "Migration record")
            record_hash = record.pop("record_hash", None)
            if record_hash != sha256(record):
                raise MigrationBlockedError("Migration record conflicts with its hash.")
            if SQLiteArtifactIndex(self._workspace.index_path).schema_version() != int(
                cast(int, record["target_schema_version"])
            ):
                raise MigrationBlockedError(
                    "Applied migration record conflicts with current state."
                )
            return {**record, "status": "already_applied"}
        plan_path = self._plans / f"{plan_id}.json"
        plan = _json(plan_path.read_bytes(), "Migration plan")
        plan_hash = plan.pop("plan_hash", None)
        if plan_hash != sha256(plan) or plan.get("migration_id") != LEGACY_INDEX.id:
            raise MigrationBlockedError("Migration plan hash or definition is invalid.")
        inventory = FilesystemHardeningRepository(self._workspace).inventory()
        if (
            plan.get("workspace_id") != inventory.workspace_id
            or plan.get("workspace_generation") != inventory.generation
        ):
            raise MigrationBlockedError("Migration plan is stale for current workspace generation.")
        if plan.get("requires_backup"):
            if backup is None:
                raise MigrationBlockedError("Canonical migration requires a verified backup.")
            verified = verify_backup(backup)
            if (
                verified["source_workspace_id"] != inventory.workspace_id
                or verified["source_generation"] != inventory.generation
            ):
                raise MigrationBlockedError("Migration backup does not match planned generation.")
        if dry_run:
            return {**plan, "plan_hash": plan_hash, "dry_run": True}
        started = _now()
        store = WorkspaceStore()
        repository = FilesystemArtifactRepository(self._workspace, store)
        indexed = IndexingService(
            repository, SQLiteArtifactIndex(self._workspace.index_path)
        ).rebuild()
        after = FilesystemHardeningRepository(self._workspace).inventory()
        if after.generation != inventory.generation:
            raise MigrationBlockedError("Derived migration changed canonical workspace state.")
        record = {
            "schema_version": 1,
            "migration_id": LEGACY_INDEX.id,
            "migration_version": LEGACY_INDEX.version,
            "kind": LEGACY_INDEX.kind,
            "plan_id": plan_id,
            "plan_hash": plan_hash,
            "workspace_generation_before": inventory.generation,
            "workspace_generation_after": after.generation,
            "backup_id": None,
            "backup_hash": None,
            "started_at": started,
            "completed_at": _now(),
            "verification_result": "PASS",
            "application_version": APPLICATION_VERSION,
            "target_schema_version": CURRENT_SCHEMA_VERSION,
            "artifacts_indexed": indexed,
        }
        _write_new(
            record_path,
            json.dumps({**record, "record_hash": sha256(record)}, sort_keys=True, indent=2).encode()
            + b"\n",
        )
        return {**record, "status": "applied"}

    @property
    def _plans(self) -> Path:
        return self._workspace.operational_root / "migrations" / "plans"

    @property
    def _records(self) -> Path:
        return self._workspace.operational_root / "migrations" / "records"
