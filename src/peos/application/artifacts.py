"""Artifact create, read, search, and verification use cases."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from peos.domain.artifacts.model import Artifact, Author, Provenance, SearchResult, StoredArtifact
from peos.domain.artifacts.validation import validate_artifact_id
from peos.domain.errors import IndexDirtyError, IndexDivergenceError, ProjectionUpdateError
from peos.domain.relations.model import materialize_links
from peos.ports.artifact_index import ArtifactIndex
from peos.ports.artifact_repository import ArtifactRepository


def _timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ArtifactService:
    def __init__(
        self,
        repository: ArtifactRepository,
        index: ArtifactIndex,
        workspace_id: str,
        workspace_command: str,
    ) -> None:
        self._repository = repository
        self._index = index
        self._workspace_id = workspace_id
        self._workspace_command = workspace_command

    def create_concept(
        self, title: str, body: str, tags: list[str], artifact_id: str | None = None
    ) -> StoredArtifact:
        identifier = artifact_id or f"art_{uuid.uuid4().hex}"
        validate_artifact_id(identifier)
        timestamp = _timestamp()
        artifact = Artifact(
            id=identifier,
            type="knowledge.concept",
            schema_version=1,
            title=title,
            status="draft",
            workspace_id=self._workspace_id,
            created_at=timestamp,
            updated_at=timestamp,
            authors=(Author(kind="human", id="user"),),
            sensitivity="private",
            tags=tuple(tags),
            links=(),
            provenance=Provenance(producer="human", run_id=None, source_refs=()),
            content_hash=None,
            body=body,
        )
        stored = self._repository.save(artifact)
        try:
            self._index.upsert(stored)
        except Exception as error:
            self._repository.write_index_dirty(stored)
            raise ProjectionUpdateError(
                "Canonical artifact was saved but index projection failed."
            ) from error
        return stored

    def get(self, artifact_id: str) -> StoredArtifact:
        self._require_healthy_index()
        projected = self._index.get(artifact_id)
        canonical = self._repository.verify(projected.canonical_path)
        if (
            canonical.artifact.id != artifact_id
            or canonical.artifact.content_hash != projected.artifact.content_hash
        ):
            raise IndexDivergenceError("Canonical artifact differs from the derived index.")
        if canonical.artifact.workspace_id != self._workspace_id:
            raise IndexDivergenceError("Canonical artifact belongs to a different workspace.")
        return canonical

    def search(self, query: str, limit: int) -> list[SearchResult]:
        self._require_healthy_index()
        results = self._index.search(query, limit)
        for result in results:
            self._repository.read(result.canonical_path)
        return results

    def verify(self, artifact_id: str) -> StoredArtifact:
        self._require_healthy_index()
        projected = self._index.get(artifact_id)
        stored = self._repository.verify(projected.canonical_path)
        canonical = {item.artifact.id: item for item in self._repository.scan()}
        for edge in materialize_links(
            stored.artifact.id, stored.artifact.links, stored.artifact.content_hash
        ):
            for endpoint in (edge.source_artifact_id, edge.target_artifact_id):
                if endpoint not in canonical:
                    raise IndexDivergenceError("Canonical artifact relation is dangling.")
                self._repository.verify(canonical[endpoint].canonical_path)
        return stored

    def _require_healthy_index(self) -> None:
        if self._repository.is_index_dirty() or not self._index.is_healthy():
            raise IndexDirtyError(
                "Index is unavailable or dirty.", f"{self._workspace_command} index rebuild"
            )
