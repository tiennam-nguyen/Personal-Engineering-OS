from pathlib import Path

import pytest

from peos.adapters.filesystem.source_object_store import FilesystemSourceObjectStore
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.domain.errors import SourceObjectCorruption


def test_object_round_trip_reuse_and_corruption(tmp_path: Path) -> None:
    workspace, _ = WorkspaceStore().initialize(tmp_path / "ws")
    store = FilesystemSourceObjectStore(workspace)
    object_hash, locator = store.put(b"raw\xffbytes")
    assert store.put(b"raw\xffbytes") == (object_hash, locator)
    assert store.read(object_hash) == b"raw\xffbytes"
    (workspace.root / locator).write_bytes(b"corrupt")
    with pytest.raises(SourceObjectCorruption):
        store.verify(object_hash)
