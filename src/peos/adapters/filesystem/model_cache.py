from __future__ import annotations

import json

from peos.adapters.filesystem.atomic import atomic_write
from peos.adapters.filesystem.workspace import Workspace
from peos.domain.errors import CacheConflictError, CacheCorruptionError
from peos.domain.runs.model import sha256


class FilesystemModelCache:
    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def locator(self, key: str) -> str:
        digest = key.removeprefix("sha256:")
        return f".peos/cache/model/{digest[:2]}/{digest}.json"

    def get(self, key: str) -> dict[str, object] | None:
        path = self._workspace.root / self.locator(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CacheCorruptionError(
                "Model cache entry is corrupt.", self.locator(key)
            ) from error
        if not isinstance(data, dict):
            raise CacheCorruptionError("Model cache entry is invalid.", self.locator(key))
        entry_hash = data.pop("entry_hash", None)
        if data.get("cache_key") != key or entry_hash != sha256(data):
            raise CacheCorruptionError("Model cache entry hash is invalid.", self.locator(key))
        data["entry_hash"] = entry_hash
        return data

    def put(self, key: str, value: dict[str, object]) -> None:
        path = self._workspace.root / self.locator(key)
        entry = {**value, "entry_hash": sha256(value)}
        if path.exists():
            if self.get(key) != entry:
                raise CacheConflictError("Existing model cache entry conflicts.")
            return
        atomic_write(
            self._workspace.staging_root,
            path,
            json.dumps(entry, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n",
        )
