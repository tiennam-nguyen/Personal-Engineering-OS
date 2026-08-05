from pathlib import Path

import pytest

from peos.adapters.filesystem.model_cache import FilesystemModelCache
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.domain.errors import CacheConflictError, CacheCorruptionError


def test_cache_round_trip_conflict_and_corruption(tmp_path: Path) -> None:
    workspace, _ = WorkspaceStore().initialize(tmp_path / "ws")
    cache = FilesystemModelCache(workspace)
    key = "sha256:" + "a" * 64
    assert cache.get(key) is None
    value: dict[str, object] = {
        "cache_key": key,
        "origin_run_id": "run_x",
        "origin_call_id": "call_x",
        "response": {},
    }
    cache.put(key, value)
    loaded = cache.get(key)
    assert loaded is not None and loaded["origin_run_id"] == "run_x"
    with pytest.raises(CacheConflictError):
        cache.put(key, value | {"origin_run_id": "run_y"})
    path = workspace.root / cache.locator(key)
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(CacheCorruptionError) as error:
        cache.get(key)
    assert error.value.recovery_action == cache.locator(key)
