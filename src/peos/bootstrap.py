"""Concrete wiring at the application edge."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from peos.adapters.filesystem.model_cache import FilesystemModelCache
from peos.adapters.filesystem.project_estate_reader import FilesystemProjectEstateReader
from peos.adapters.filesystem.protocol_repository import FilesystemProtocolRepository
from peos.adapters.filesystem.repository import FilesystemArtifactRepository
from peos.adapters.filesystem.run_repository import FilesystemRunRepository
from peos.adapters.filesystem.source_object_store import FilesystemSourceObjectStore
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.adapters.filesystem.workspace_lock import WorkspaceLock
from peos.adapters.models.mock import DeterministicMockGateway
from peos.adapters.sqlite.artifact_index import SQLiteArtifactIndex
from peos.application.artifacts import ArtifactService
from peos.application.context import ContextCompiler
from peos.application.indexing import IndexingService
from peos.application.modeling import ModelCallService
from peos.application.project import ProjectService
from peos.application.research import ResearchService
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


def open_research_workspace(
    root: Path, fault_injector: FaultInjector | None = None
) -> ResearchService:
    store = WorkspaceStore()
    workspace = store.open(root)
    artifacts = FilesystemArtifactRepository(workspace, store)
    index = SQLiteArtifactIndex(workspace.index_path)
    return ResearchService(
        workspace.root,
        workspace.workspace_id,
        FilesystemRunRepository(workspace),
        artifacts,
        index,
        FilesystemSourceObjectStore(workspace),
        FilesystemProtocolRepository(workspace.root),
        FilesystemModelCache(workspace),
        DeterministicMockGateway(),
        fault_injector,
    )


def open_project_workspace(
    root: Path, fault_injector: FaultInjector | None = None
) -> ProjectService:
    store = WorkspaceStore()
    workspace = store.open(root)
    artifacts = FilesystemArtifactRepository(workspace, store)
    return ProjectService(
        workspace.workspace_id,
        FilesystemRunRepository(workspace),
        artifacts,
        SQLiteArtifactIndex(workspace.index_path),
        FilesystemSourceObjectStore(workspace),
        FilesystemProtocolRepository(workspace.root),
        FilesystemModelCache(workspace),
        DeterministicMockGateway(),
        FilesystemProjectEstateReader,
        fault_injector,
    )


def open_run_for_id(root: Path, run_id: str) -> RunService | ResearchService | ProjectService:
    workspace = WorkspaceStore().open(root)
    manifest = FilesystemRunRepository(workspace).read_manifest(run_id)
    workflow = manifest.get("workflow")
    if isinstance(workflow, dict) and workflow.get("name") == "research.compile-plain-text":
        return open_research_workspace(root)
    if isinstance(workflow, dict) and str(workflow.get("name", "")).startswith("project."):
        return open_project_workspace(root)
    return open_run_workspace(root)


@contextmanager
def mutation_lock(root: Path, command: str) -> Iterator[None]:
    """Acquire only at bootstrap so CLI/application remain adapter-independent."""
    workspace = WorkspaceStore().open(root)
    with WorkspaceLock(workspace.locks_root / "workspace.lock", command):
        yield
