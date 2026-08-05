from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from peos.adapters.filesystem.repository import FilesystemArtifactRepository
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.application.artifacts import ArtifactService
from peos.application.indexing import IndexingService
from peos.bootstrap import initialize_workspace, open_workspace
from peos.domain.errors import (
    DuplicateArtifactId,
    IntegrityVerificationError,
    ProjectionUpdateError,
    ValidationError,
)
from peos.ports.artifact_index import ArtifactIndex


def _init(root: Path) -> tuple[ArtifactService, IndexingService]:
    artifacts, indexing, _, _ = initialize_workspace(root)
    return artifacts, indexing


def test_valid_artifact_round_trip(tmp_path: Path) -> None:
    artifacts, _ = _init(tmp_path)
    stored = artifacts.create_concept("Title", "Body term", ["one"])
    assert (tmp_path / stored.canonical_path).exists()
    assert artifacts.get(stored.artifact.id).artifact.body == "Body term\n"
    assert artifacts.search("body term", 20)[0].id == stored.artifact.id
    verified = artifacts.verify(stored.artifact.id)
    assert verified.artifact.content_hash == stored.artifact.content_hash


def test_invalid_schema_is_rejected_without_side_effects(tmp_path: Path) -> None:
    artifacts, _ = _init(tmp_path)
    with pytest.raises(ValidationError):
        artifacts.create_concept(" ", "Body", [])
    assert not list((tmp_path / "artifacts" / "knowledge").glob("*.md"))


def test_projection_failure_preserves_readable_canonical_artifact(tmp_path: Path) -> None:
    store = WorkspaceStore()
    workspace, _ = store.initialize(tmp_path)
    repository = FilesystemArtifactRepository(workspace, store)

    class FailingIndex:
        def upsert(self, stored: object) -> None:
            raise RuntimeError("injected")

    index = cast(ArtifactIndex, FailingIndex())
    service = ArtifactService(repository, index, workspace.workspace_id, "peos")
    with pytest.raises(ProjectionUpdateError):
        service.create_concept("Title", "Body", [])
    canonical = next((tmp_path / "artifacts" / "knowledge").glob("*.md"))
    assert repository.verify(canonical.relative_to(tmp_path).as_posix()).artifact.id
    assert (tmp_path / ".peos" / "INDEX_DIRTY").exists()


def test_rebuild_restores_lookup_and_search_after_index_deletion(tmp_path: Path) -> None:
    artifacts, indexing = _init(tmp_path)
    stored = artifacts.create_concept("Rebuild", "Recover canonical", [])
    original = (tmp_path / stored.canonical_path).read_bytes()
    (tmp_path / ".peos" / "index.sqlite3").unlink()
    assert indexing.rebuild() == 1
    restored, _ = open_workspace(tmp_path)
    assert restored.get(stored.artifact.id).artifact.content_hash == stored.artifact.content_hash
    assert restored.search("recover", 20)[0].id == stored.artifact.id
    assert (tmp_path / stored.canonical_path).read_bytes() == original


def test_duplicate_id_is_rejected_without_overwrite(tmp_path: Path) -> None:
    artifacts, _ = _init(tmp_path)
    identifier = "art_" + "1" * 32
    stored = artifacts.create_concept("First", "Original", [], identifier)
    original = (tmp_path / stored.canonical_path).read_bytes()
    with pytest.raises(DuplicateArtifactId):
        artifacts.create_concept("Second", "Changed", [], identifier)
    assert (tmp_path / stored.canonical_path).read_bytes() == original


def test_tampered_artifact_fails_independent_hash_verification(tmp_path: Path) -> None:
    artifacts, _ = _init(tmp_path)
    stored = artifacts.create_concept("Title", "Original", [])
    path = tmp_path / stored.canonical_path
    path.write_bytes(path.read_bytes().replace(b"Original", b"Tampered"))
    with pytest.raises(IntegrityVerificationError):
        artifacts.verify(stored.artifact.id)


def test_failed_rebuild_preserves_previous_usable_index(tmp_path: Path) -> None:
    artifacts, indexing = _init(tmp_path)
    stored = artifacts.create_concept("Stable", "Valid", [])
    bad = tmp_path / "artifacts" / "knowledge" / "art_bad.md"
    bad.write_text("not front matter\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        indexing.rebuild()
    assert artifacts.get(stored.artifact.id).artifact.id == stored.artifact.id


def test_staging_files_are_not_treated_as_canonical_artifacts(tmp_path: Path) -> None:
    artifacts, indexing = _init(tmp_path)
    stored = artifacts.create_concept("Title", "Body", [])
    staging = tmp_path / ".peos" / "staging" / "art_fake.md"
    staging.write_text("bad", encoding="utf-8")
    assert indexing.rebuild() == 1
    assert artifacts.get(stored.artifact.id).artifact.id == stored.artifact.id
