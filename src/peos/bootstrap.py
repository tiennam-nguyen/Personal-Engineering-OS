"""Concrete wiring at the application edge."""

from __future__ import annotations

from pathlib import Path

from peos.adapters.filesystem.repository import FilesystemArtifactRepository
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.adapters.sqlite.artifact_index import SQLiteArtifactIndex
from peos.application.artifacts import ArtifactService
from peos.application.indexing import IndexingService


def initialize_workspace(root: Path) -> tuple[ArtifactService, IndexingService, str, bool]:
    store = WorkspaceStore()
    workspace, created = store.initialize(root)
    index = SQLiteArtifactIndex(workspace.index_path)
    if not index.is_healthy():
        index.initialize()
    repository = FilesystemArtifactRepository(workspace, store)
    command = f"peos --workspace {workspace.root}"
    artifacts = ArtifactService(repository, index, workspace.workspace_id, command)
    return artifacts, IndexingService(repository, index), workspace.workspace_id, created


def open_workspace(root: Path) -> tuple[ArtifactService, IndexingService]:
    store = WorkspaceStore()
    workspace = store.open(root)
    repository = FilesystemArtifactRepository(workspace, store)
    index = SQLiteArtifactIndex(workspace.index_path)
    command = f"peos --workspace {workspace.root}"
    artifacts = ArtifactService(repository, index, workspace.workspace_id, command)
    return artifacts, IndexingService(repository, index)
