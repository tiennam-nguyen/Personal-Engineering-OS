from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import cast

import pytest

from peos.adapters.filesystem.hardening import (
    FilesystemHardeningRepository,
    restore_backup,
    verify_backup,
)
from peos.adapters.filesystem.source_object_store import FilesystemSourceObjectStore
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.bootstrap import initialize_workspace
from peos.domain.errors import BackupConflictError, HardeningIntegrityError
from peos.ports.fault_injector import SimulatedInterruption, SingleCheckpointFaultInjector


def populated(tmp_path: Path) -> tuple[Path, FilesystemHardeningRepository]:
    root = tmp_path / "workspace"
    artifacts, _, _, _ = initialize_workspace(root)
    artifacts.create_concept("One", "Canonical one", ["release"])
    artifacts.create_concept("Two", "Canonical two", ["release"])
    workspace = WorkspaceStore().open(root)
    FilesystemSourceObjectStore(workspace).put(b"synthetic release object\n")
    protocol = root / "protocols" / "sample" / "1.0.0.md"
    protocol.parent.mkdir(parents=True)
    protocol.write_text("# Synthetic protocol\n", encoding="utf-8", newline="")
    return root, FilesystemHardeningRepository(workspace)


def test_inventory_ignores_derived_state_and_tracks_canonical_changes(tmp_path: Path) -> None:
    root, repository = populated(tmp_path)
    before = repository.inventory()
    (root / ".peos" / "cache" / "x").parent.mkdir(parents=True)
    (root / ".peos" / "cache" / "x").write_text("derived")
    (root / ".peos" / "index.sqlite3").touch()
    assert repository.inventory().generation == before.generation
    artifact = next((root / "artifacts" / "knowledge").glob("*.md"))
    artifact.write_bytes(artifact.read_bytes() + b"\n")
    assert repository.inventory().generation != before.generation


def test_backup_create_verify_restore_preserves_inventory_and_rebuilds(tmp_path: Path) -> None:
    root, repository = populated(tmp_path)
    source = repository.inventory()
    backup = tmp_path / "backup"
    created = repository.create_backup(backup, False)
    verified = verify_backup(backup)
    restored = tmp_path / "restored"
    result = restore_backup(backup, restored, False)
    restored_inventory = FilesystemHardeningRepository(WorkspaceStore().open(restored)).inventory()

    assert created["valid"] is verified["valid"] is True
    assert verified["object_count"] == 1
    assert source.entries == restored_inventory.entries
    assert source.generation == result["restored_generation"] == restored_inventory.generation
    assert cast(dict[str, object], result["doctor"])["healthy"] is True
    assert not (backup / "payload/.peos/index.sqlite3").exists()
    assert not (backup / "payload/.peos/cache").exists()
    assert (restored / ".peos/index.sqlite3").exists()


def test_backup_dry_run_and_overwrite_restore_ruin_gates(tmp_path: Path) -> None:
    _, repository = populated(tmp_path)
    backup = tmp_path / "backup"
    assert repository.create_backup(backup, True)["dry_run"] is True
    assert not backup.exists()
    repository.create_backup(backup, False)
    original = (backup / "manifest.json").read_bytes()
    with pytest.raises(BackupConflictError):
        repository.create_backup(backup, False)
    assert (backup / "manifest.json").read_bytes() == original
    target = tmp_path / "target"
    target.mkdir()
    with pytest.raises(BackupConflictError):
        restore_backup(backup, target, False)
    dry_target = tmp_path / "dry-target"
    assert restore_backup(backup, dry_target, True)["dry_run"] is True
    assert not dry_target.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("format_version", 99),
        ("backup_id", "bad"),
        ("source_generation", "sha256:" + "0" * 64),
    ],
)
def test_backup_manifest_tamper_fails(tmp_path: Path, field: str, value: object) -> None:
    _, repository = populated(tmp_path)
    backup = tmp_path / "backup"
    repository.create_backup(backup, False)
    manifest = json.loads((backup / "manifest.json").read_text())
    manifest[field] = value
    (backup / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(HardeningIntegrityError):
        verify_backup(backup)


def test_backup_payload_object_traversal_duplicate_and_symlink_tamper_fail(tmp_path: Path) -> None:
    _, repository = populated(tmp_path)
    backup = tmp_path / "backup"
    repository.create_backup(backup, False)
    payload_file = next((backup / "payload/artifacts").rglob("*.md"))
    payload_file.write_bytes(payload_file.read_bytes() + b"tamper")
    with pytest.raises(HardeningIntegrityError):
        verify_backup(backup)

    shutil.rmtree(backup)
    repository.create_backup(backup, False)
    manifest = json.loads((backup / "manifest.json").read_text())
    manifest["files"][0]["path"] = "../escape"
    (backup / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(HardeningIntegrityError):
        verify_backup(backup)

    shutil.rmtree(backup)
    repository.create_backup(backup, False)
    manifest = json.loads((backup / "manifest.json").read_text())
    manifest["files"].append(dict(manifest["files"][0]))
    (backup / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(HardeningIntegrityError):
        verify_backup(backup)


def test_backup_secret_sentinel_is_never_materialized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, repository = populated(tmp_path)
    sentinel = "PEOS_TEST_SECRET_VALUE_7f42"
    monkeypatch.setenv("PEOS_API_SECRET", sentinel)
    backup = tmp_path / "backup"
    output = repository.create_backup(backup, False)
    combined = json.dumps(output) + "".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in backup.rglob("*")
        if path.is_file()
    )
    assert sentinel not in combined


@pytest.mark.parametrize(
    "checkpoint",
    [
        "after_backup_inventory",
        "during_backup_payload_copy",
        "after_backup_payload_copy",
        "after_backup_manifest",
    ],
)
def test_backup_interruption_has_no_visible_partial_backup(tmp_path: Path, checkpoint: str) -> None:
    _, _ = populated(tmp_path)
    workspace = WorkspaceStore().open(tmp_path / "workspace")
    backup = tmp_path / "backup"
    repository = FilesystemHardeningRepository(workspace, SingleCheckpointFaultInjector(checkpoint))
    with pytest.raises(SimulatedInterruption):
        repository.create_backup(backup, False)
    assert not backup.exists()
    assert not list(tmp_path.glob(".backup.staging-*"))


@pytest.mark.parametrize(
    "checkpoint",
    [
        "after_restore_backup_verified",
        "during_restore_staging_copy",
        "after_restore_copy",
        "after_restore_generation_verified",
    ],
)
def test_restore_interruption_before_visibility_has_no_target(
    tmp_path: Path, checkpoint: str
) -> None:
    _, repository = populated(tmp_path)
    backup = tmp_path / "backup"
    repository.create_backup(backup, False)
    target = tmp_path / "restored"
    with pytest.raises(SimulatedInterruption):
        restore_backup(backup, target, False, SingleCheckpointFaultInjector(checkpoint))
    assert not target.exists()
    assert not list(tmp_path.glob(".restored.restore-*"))
