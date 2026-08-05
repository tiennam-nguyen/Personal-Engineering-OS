"""Filesystem canonical artifact repository."""

from __future__ import annotations

from pathlib import Path

from peos.adapters.filesystem.atomic import atomic_write
from peos.adapters.filesystem.codec import calculate_hash, serialize, verify
from peos.adapters.filesystem.workspace import Workspace, WorkspaceStore
from peos.domain.artifacts.model import Artifact, StoredArtifact
from peos.domain.artifacts.validation import validate_artifact
from peos.domain.errors import ArtifactNotFound, DuplicateArtifactId


class FilesystemArtifactRepository:
    def __init__(self, workspace: Workspace, workspace_store: WorkspaceStore) -> None:
        self._workspace = workspace
        self._workspace_store = workspace_store

    def save(self, artifact: Artifact) -> StoredArtifact:
        validated = validate_artifact(
            artifact, expected_workspace_id=self._workspace.workspace_id, require_hash=False
        )
        path = self._path_for_id(validated.id)
        relative = path.relative_to(self._workspace.root).as_posix()
        if path.exists():
            raise DuplicateArtifactId("Artifact ID already exists.")
        hashed = Artifact(**{**validated.__dict__, "content_hash": calculate_hash(validated)})
        atomic_write(self._workspace.staging_root, path, serialize(hashed))
        return self.verify(relative)

    def read(self, canonical_path: str) -> StoredArtifact:
        path = self._resolve_canonical_path(canonical_path)
        if not path.exists():
            raise ArtifactNotFound("Canonical artifact was not found.")
        return verify(path.read_bytes(), canonical_path)

    def verify(self, canonical_path: str) -> StoredArtifact:
        return self.read(canonical_path)

    def scan(self) -> list[StoredArtifact]:
        records: list[StoredArtifact] = []
        for path in sorted(
            self._workspace.root.glob("artifacts/**/*.md"),
            key=lambda item: item.relative_to(self._workspace.root).as_posix(),
        ):
            relative = path.relative_to(self._workspace.root).as_posix()
            records.append(self.verify(relative))
        return records

    def write_index_dirty(self, stored: StoredArtifact) -> None:
        self._workspace_store.write_dirty(
            self._workspace,
            {
                "artifact_id": stored.artifact.id,
                "canonical_path": stored.canonical_path,
                "content_hash": stored.artifact.content_hash or "",
                "error_code": "projection_update_failed",
            },
        )

    def is_index_dirty(self) -> bool:
        return self._workspace.dirty_path.exists()

    def remove_index_dirty(self) -> None:
        self._workspace_store.remove_dirty(self._workspace)

    def _path_for_id(self, artifact_id: str) -> Path:
        return self._workspace.artifact_root / f"{artifact_id}.md"

    def _resolve_canonical_path(self, canonical_path: str) -> Path:
        path = (self._workspace.root / Path(canonical_path)).resolve()
        artifacts = (self._workspace.root / "artifacts").resolve()
        if artifacts not in path.parents:
            raise ArtifactNotFound("Canonical artifact path is outside the workspace artifacts.")
        return path
