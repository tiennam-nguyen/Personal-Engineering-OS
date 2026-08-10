from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import pytest

from peos.adapters.filesystem.hardening import FilesystemHardeningRepository
from peos.adapters.filesystem.source_object_store import FilesystemSourceObjectStore
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.bootstrap import initialize_workspace
from peos.cli.main import main
from peos.domain.errors import GarbageCollectionBlockedError


def test_gc_retains_referenced_object_and_quarantines_only_orphan(tmp_path: Path) -> None:
    artifacts, _, _, _ = initialize_workspace(tmp_path)
    workspace = WorkspaceStore().open(tmp_path)
    objects = FilesystemSourceObjectStore(workspace)
    referenced_hash, referenced_path = objects.put(b"referenced\n")
    orphan_hash, orphan_path = objects.put(b"orphan\n")
    artifacts.create_concept("Reference", referenced_hash, [])
    hardening = FilesystemHardeningRepository(workspace)
    plan = hardening.gc_plan()
    candidates = cast(list[dict[str, object]], plan["candidates"])
    candidate_paths = {item["path"] for item in candidates}
    assert orphan_path in candidate_paths
    assert referenced_path not in candidate_paths
    with pytest.raises(GarbageCollectionBlockedError):
        hardening.gc_execute(str(plan["plan_id"]), tmp_path / "missing", False, False)
    backup = tmp_path / ".peos/backups/gc"
    hardening.create_backup(backup, False)
    result = hardening.gc_execute(str(plan["plan_id"]), backup, True, False)
    assert result["permanent_delete"] is False
    assert objects.exists(referenced_hash)
    assert not objects.exists(orphan_hash)
    assert (tmp_path / ".peos/quarantine" / str(plan["plan_id"]) / orphan_path).exists()
    assert (
        hardening.gc_execute(str(plan["plan_id"]), backup, True, False)["moves"] == result["moves"]
    )


def test_gc_stale_plan_and_rereference_fail_closed(tmp_path: Path) -> None:
    artifacts, _, _, _ = initialize_workspace(tmp_path)
    workspace = WorkspaceStore().open(tmp_path)
    objects = FilesystemSourceObjectStore(workspace)
    orphan_hash, _ = objects.put(b"orphan\n")
    hardening = FilesystemHardeningRepository(workspace)
    plan = hardening.gc_plan()
    artifacts.create_concept("Now referenced", orphan_hash, [])
    backup = tmp_path / ".peos/backups/stale"
    hardening.create_backup(backup, False)
    with pytest.raises(GarbageCollectionBlockedError):
        hardening.gc_execute(str(plan["plan_id"]), backup, True, False)
    assert objects.exists(orphan_hash)


def test_expired_cache_is_candidate_but_current_cache_is_retained(tmp_path: Path) -> None:
    initialize_workspace(tmp_path)
    workspace = WorkspaceStore().open(tmp_path)
    cache = tmp_path / ".peos/cache/model"
    cache.mkdir(parents=True)
    old, current = cache / "old.json", cache / "current.json"
    old.write_text("old")
    current.write_text("current")
    os.utime(old, (1, 1))
    plan = FilesystemHardeningRepository(workspace).gc_plan()
    candidates = cast(list[dict[str, object]], plan["candidates"])
    retained = cast(list[dict[str, object]], plan["retained"])
    assert any(str(item["path"]).endswith("old.json") for item in candidates)
    assert any(str(item["path"]).endswith("current.json") for item in retained)


def test_doctor_is_read_only_and_reports_index_recovery(tmp_path: Path) -> None:
    initialize_workspace(tmp_path)
    workspace = WorkspaceStore().open(tmp_path)
    hardening = FilesystemHardeningRepository(workspace)
    before = hardening.inventory()
    assert hardening.doctor()["healthy"] is True
    assert hardening.inventory() == before
    (tmp_path / ".peos/index.sqlite3").unlink()
    result = hardening.doctor()
    assert result["healthy"] is False
    checks = cast(list[dict[str, object]], result["checks"])
    index = next(item for item in checks if item["name"] == "derived_index")
    assert index["status"] == "FAIL" and "index rebuild" in str(index["recovery"])


def test_doctor_does_not_recreate_missing_operational_directories(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    initialize_workspace(tmp_path)
    staging = tmp_path / ".peos/staging"
    staging.rmdir()
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert main(["--workspace", str(tmp_path), "doctor"]) == 0
    capsys.readouterr()
    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert after == before
