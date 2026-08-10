from __future__ import annotations

from pathlib import Path

import pytest

from peos.adapters.filesystem.hardening import (
    FilesystemHardeningRepository,
    restore_backup,
    verify_backup,
)
from peos.adapters.filesystem.migrations import FilesystemMigrationRepository
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.adapters.sqlite.artifact_index import CURRENT_SCHEMA_VERSION, SQLiteArtifactIndex
from peos.application.migrations import MigrationDefinition, MigrationService
from peos.bootstrap import initialize_workspace
from peos.domain.errors import MigrationBlockedError, ProjectionUpdateError


def service(root: Path) -> tuple[MigrationService, FilesystemHardeningRepository]:
    workspace = WorkspaceStore().open(root)
    return (
        MigrationService(FilesystemMigrationRepository(workspace)),
        FilesystemHardeningRepository(workspace),
    )


def test_current_m8_index_schema_needs_no_fake_migration(tmp_path: Path) -> None:
    initialize_workspace(tmp_path)
    migrations, _ = service(tmp_path)
    status = migrations.status()
    assert status["current_index_schema_version"] == CURRENT_SCHEMA_VERSION == 2
    assert migrations.plan()["already_current"] is True


def test_legacy_or_missing_index_rebuild_migration_preserves_canonical_bytes(
    tmp_path: Path,
) -> None:
    artifacts, _, _, _ = initialize_workspace(tmp_path)
    stored = artifacts.create_concept("Legacy", "Canonical bytes", [])
    canonical = tmp_path / stored.canonical_path
    before = canonical.read_bytes()
    (tmp_path / ".peos/index.sqlite3").unlink()
    migrations, hardening = service(tmp_path)
    generation = hardening.inventory().generation
    plan = migrations.plan()
    assert plan["workspace_generation"] == generation
    with pytest.raises(MigrationBlockedError):
        migrations.apply(str(plan["plan_id"]), None, confirmed=False, dry_run=False)
    result = migrations.apply(str(plan["plan_id"]), None, confirmed=True, dry_run=False)
    assert result["status"] == "applied"
    assert canonical.read_bytes() == before
    assert SQLiteArtifactIndex(tmp_path / ".peos/index.sqlite3").schema_version() == 2
    assert (
        migrations.apply(str(plan["plan_id"]), None, confirmed=True, dry_run=False)["status"]
        == "already_applied"
    )


def test_stale_migration_plan_fails_before_rebuild(tmp_path: Path) -> None:
    artifacts, _, _, _ = initialize_workspace(tmp_path)
    (tmp_path / ".peos/index.sqlite3").unlink()
    migrations, _ = service(tmp_path)
    plan = migrations.plan()
    with pytest.raises(ProjectionUpdateError):
        artifacts.create_concept("New", "Generation change", [])
    with pytest.raises(MigrationBlockedError):
        migrations.apply(str(plan["plan_id"]), None, confirmed=True, dry_run=False)


class TestCanonicalMigrationRepository:
    """Test-only registered canonical migration proving the generic ruin-gate contract."""

    __test__ = False
    definition = MigrationDefinition(
        "test.canonical-marker",
        "1.0.0",
        "canonical",
        "REVERSIBLE_WRITE",
        "Append a test marker to MAP.md.",
        1,
        2,
        True,
    )

    def __init__(self, root: Path) -> None:
        self.root = root
        self.hardening = FilesystemHardeningRepository(WorkspaceStore().open(root))
        self.generation = self.hardening.inventory().generation
        self.applied = False

    def status(self) -> dict[str, object]:
        return {"status": "applied" if self.applied else "migration_available"}

    def plan(self) -> dict[str, object]:
        return {
            "plan_id": "test_canonical_plan",
            "migration_id": self.definition.id,
            "requires_backup": True,
            "workspace_generation": self.generation,
        }

    def apply(
        self, plan_id: str, backup: Path | None, confirmed: bool, dry_run: bool
    ) -> dict[str, object]:
        if plan_id != "test_canonical_plan" or not confirmed or backup is None:
            raise MigrationBlockedError("Canonical migration requires confirmation and backup.")
        if self.applied:
            return {"status": "already_applied", "migration_id": self.definition.id}
        verified = verify_backup(backup)
        current = self.hardening.inventory()
        if (
            verified["source_workspace_id"] != current.workspace_id
            or verified["source_generation"] != self.generation
            or current.generation != self.generation
        ):
            raise MigrationBlockedError("Canonical migration backup generation mismatch.")
        if dry_run:
            return {"dry_run": True}
        marker = self.root / "MAP.md"
        marker.write_bytes(marker.read_bytes() + b"\nTEST MIGRATION MARKER\n")
        self.applied = True
        return {"status": "applied", "migration_id": self.definition.id}


def test_canonical_migration_requires_exact_verified_backup_and_restores(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    initialize_workspace(root)
    (root / "MAP.md").write_text("# Map\n", encoding="utf-8")
    repository = TestCanonicalMigrationRepository(root)
    migrations = MigrationService(repository)
    plan = migrations.plan()
    with pytest.raises(MigrationBlockedError):
        migrations.apply(str(plan["plan_id"]), None, confirmed=True, dry_run=False)
    backup = tmp_path / "backup"
    repository.hardening.create_backup(backup, False)
    before = (root / "MAP.md").read_bytes()
    assert (
        migrations.apply(str(plan["plan_id"]), backup, confirmed=True, dry_run=False)["status"]
        == "applied"
    )
    assert (root / "MAP.md").read_bytes() != before
    assert (
        migrations.apply(str(plan["plan_id"]), backup, confirmed=True, dry_run=False)["status"]
        == "already_applied"
    )
    restored = tmp_path / "restored"
    restore_backup(backup, restored, False)
    assert (restored / "MAP.md").read_bytes() == before
