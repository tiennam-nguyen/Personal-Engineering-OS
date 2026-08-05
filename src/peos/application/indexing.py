"""Index rebuild orchestration."""

from __future__ import annotations

from peos.ports.artifact_index import ArtifactIndex
from peos.ports.artifact_repository import ArtifactRepository


class IndexingService:
    def __init__(self, repository: ArtifactRepository, index: ArtifactIndex) -> None:
        self._repository = repository
        self._index = index

    def rebuild(self) -> int:
        records = self._repository.scan()
        count = self._index.rebuild(records)
        self._repository.remove_index_dirty()
        return count
