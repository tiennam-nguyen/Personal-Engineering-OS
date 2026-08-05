"""Derived artifact projection contract."""

from __future__ import annotations

from typing import Protocol

from peos.domain.artifacts.model import SearchResult, StoredArtifact


class ArtifactIndex(Protocol):
    def initialize(self) -> None: ...

    def upsert(self, stored: StoredArtifact) -> None: ...

    def get(self, artifact_id: str) -> StoredArtifact: ...

    def search(self, query: str, limit: int) -> list[SearchResult]: ...

    def rebuild(self, records: list[StoredArtifact]) -> int: ...

    def is_healthy(self) -> bool: ...
