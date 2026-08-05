"""Concrete wiring at the application edge."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from peos.adapters.filesystem.model_cache import FilesystemModelCache
from peos.adapters.filesystem.protocol_repository import FilesystemProtocolRepository
from peos.adapters.filesystem.repository import FilesystemArtifactRepository
from peos.adapters.filesystem.run_repository import FilesystemRunRepository
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.adapters.filesystem.workspace_lock import WorkspaceLock
from peos.adapters.models.mock import DeterministicMockGateway
from peos.adapters.sqlite.artifact_index import SQLiteArtifactIndex
from peos.application.artifacts import ArtifactService
from peos.application.context import ContextCompiler
from peos.application.indexing import IndexingService
from peos.application.modeling import ModelCallService
from peos.application.runs import RunService
from peos.ports.fault_injector import FaultInjector


def initialize_workspace(root: Path) -> tuple[ArtifactService, IndexingService, str, bool]:
    store = WorkspaceStore()
    root = root.resolve()
    with WorkspaceLock(root / ".peos" / "locks" / "workspace.lock", "init"):
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


def open_run_workspace(root: Path, fault_injector: FaultInjector | None = None) -> RunService:
    store = WorkspaceStore()
    workspace = store.open(root)
    artifacts = FilesystemArtifactRepository(workspace, store)
    index = SQLiteArtifactIndex(workspace.index_path)
    modeling = ModelCallService(
        FilesystemProtocolRepository(workspace.root),
        ContextCompiler(artifacts, index),
        FilesystemModelCache(workspace),
        DeterministicMockGateway(),
    )
    return RunService(
        FilesystemRunRepository(workspace),
        artifacts,
        index,
        workspace.workspace_id,
        fault_injector,
        modeling,
    )


def open_protocol_workspace(root: Path) -> FilesystemProtocolRepository:
    workspace = WorkspaceStore().open(root)
    return FilesystemProtocolRepository(workspace.root)


@contextmanager
def mutation_lock(root: Path, command: str) -> Iterator[None]:
    """Acquire only at bootstrap so CLI/application remain adapter-independent."""
    workspace = WorkspaceStore().open(root)
    with WorkspaceLock(workspace.locks_root / "workspace.lock", command):
        yield
