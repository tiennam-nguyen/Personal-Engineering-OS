"""Filesystem content-addressed immutable source objects."""

from __future__ import annotations

import hashlib

from peos.adapters.filesystem.atomic import atomic_write
from peos.adapters.filesystem.workspace import Workspace
from peos.domain.errors import SourceObjectCorruption


class FilesystemSourceObjectStore:
    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def locator(self, object_hash: str) -> str:
        digest = object_hash.removeprefix("sha256:")
        return f".peos/objects/sha256/{digest[:2]}/{digest}"

    def put(self, raw: bytes) -> tuple[str, str]:
        object_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
        path = self._workspace.root / self.locator(object_hash)
        if path.exists():
            if path.read_bytes() != raw:
                raise SourceObjectCorruption("Existing source object conflicts.")
        else:
            atomic_write(self._workspace.staging_root, path, raw)
        self.verify(object_hash)
        return object_hash, self.locator(object_hash)

    def read(self, object_hash: str) -> bytes:
        path = (self._workspace.root / self.locator(object_hash)).resolve()
        root = (self._workspace.root / ".peos" / "objects" / "sha256").resolve()
        if root not in path.parents:
            raise SourceObjectCorruption("Source object locator escapes object store.")
        try:
            return path.read_bytes()
        except OSError as error:
            raise SourceObjectCorruption("Source object cannot be read.") from error

    def verify(self, object_hash: str) -> str:
        raw = self.read(object_hash)
        actual = "sha256:" + hashlib.sha256(raw).hexdigest()
        if actual != object_hash:
            raise SourceObjectCorruption("Source object hash mismatch.")
        return self.locator(object_hash)

    def exists(self, object_hash: str) -> bool:
        return (self._workspace.root / self.locator(object_hash)).exists()
