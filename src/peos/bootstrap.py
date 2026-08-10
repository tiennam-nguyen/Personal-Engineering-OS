"""Concrete wiring at the application edge."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from peos.adapters.filesystem.evaluation_repository import FilesystemEvaluationSuiteRepository
from peos.adapters.filesystem.hardening import (
    FilesystemHardeningRepository,
    restore_backup,
    verify_backup,
)
from peos.adapters.filesystem.migrations import FilesystemMigrationRepository
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
from peos.application.crossflow import CrossflowService
from peos.application.evaluation_candidates import CandidateCatalog
from peos.application.evaluations import EvaluationService
from peos.application.graph import GraphService
from peos.application.hardening import HardeningService
from peos.application.indexing import IndexingService
from peos.application.learning import LearningService
from peos.application.migrations import MigrationService
from peos.application.modeling import ModelCallService
from peos.application.project import ProjectService
from peos.application.qualifications import QualificationService
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
    runs = FilesystemRunRepository(workspace)
    qualifications = QualificationService(
        FilesystemEvaluationSuiteRepository(workspace.root), artifacts, runs
    )
    modeling = ModelCallService(
        FilesystemProtocolRepository(workspace.root),
        ContextCompiler(artifacts, index),
        FilesystemModelCache(workspace),
        DeterministicMockGateway(),
        qualifications,
    )
    return RunService(
        runs,
        artifacts,
        index,
        workspace.workspace_id,
        fault_injector,
        modeling,
    )


def open_protocol_workspace(root: Path) -> FilesystemProtocolRepository:
    workspace = WorkspaceStore().open(root)
    return FilesystemProtocolRepository(workspace.root)


def open_hardening_workspace(
    root: Path, fault_injector: FaultInjector | None = None
) -> HardeningService:
    workspace = WorkspaceStore().open(root, ensure_layout=False)
    return HardeningService(FilesystemHardeningRepository(workspace, fault_injector))


def verify_backup_path(path: Path) -> dict[str, object]:
    return verify_backup(path)


def open_migration_workspace(root: Path) -> MigrationService:
    workspace = WorkspaceStore().open(root, ensure_layout=False)
    return MigrationService(FilesystemMigrationRepository(workspace))


def restore_backup_path(
    backup: Path, target: Path, dry_run: bool = False, fault_injector: FaultInjector | None = None
) -> dict[str, object]:
    return restore_backup(backup, target, dry_run, fault_injector)


def open_research_workspace(
    root: Path, fault_injector: FaultInjector | None = None
) -> ResearchService:
    store = WorkspaceStore()
    workspace = store.open(root)
    artifacts = FilesystemArtifactRepository(workspace, store)
    index = SQLiteArtifactIndex(workspace.index_path)
    runs = FilesystemRunRepository(workspace)
    qualifications = QualificationService(
        FilesystemEvaluationSuiteRepository(workspace.root), artifacts, runs
    )
    return ResearchService(
        workspace.root,
        workspace.workspace_id,
        runs,
        artifacts,
        index,
        FilesystemSourceObjectStore(workspace),
        FilesystemProtocolRepository(workspace.root),
        FilesystemModelCache(workspace),
        DeterministicMockGateway(),
        qualifications,
        fault_injector,
    )


def open_project_workspace(
    root: Path, fault_injector: FaultInjector | None = None
) -> ProjectService:
    store = WorkspaceStore()
    workspace = store.open(root)
    artifacts = FilesystemArtifactRepository(workspace, store)
    runs = FilesystemRunRepository(workspace)
    qualifications = QualificationService(
        FilesystemEvaluationSuiteRepository(workspace.root), artifacts, runs
    )
    return ProjectService(
        workspace.workspace_id,
        runs,
        artifacts,
        SQLiteArtifactIndex(workspace.index_path),
        FilesystemSourceObjectStore(workspace),
        FilesystemProtocolRepository(workspace.root),
        FilesystemModelCache(workspace),
        DeterministicMockGateway(),
        qualifications,
        FilesystemProjectEstateReader,
        fault_injector,
    )


def open_learning_workspace(
    root: Path, fault_injector: FaultInjector | None = None
) -> LearningService:
    store = WorkspaceStore()
    workspace = store.open(root)
    return LearningService(
        workspace.workspace_id,
        FilesystemRunRepository(workspace),
        FilesystemArtifactRepository(workspace, store),
        SQLiteArtifactIndex(workspace.index_path),
        fault_injector,
    )


def open_graph_workspace(root: Path) -> GraphService:
    store = WorkspaceStore()
    workspace = store.open(root)
    repository = FilesystemArtifactRepository(workspace, store)
    index = SQLiteArtifactIndex(workspace.index_path)
    return GraphService(repository, index, index, f"peos --workspace {workspace.root}")


def open_crossflow_workspace(
    root: Path, fault_injector: FaultInjector | None = None
) -> CrossflowService:
    store = WorkspaceStore()
    workspace = store.open(root)
    repository = FilesystemArtifactRepository(workspace, store)
    index = SQLiteArtifactIndex(workspace.index_path)
    return CrossflowService(
        workspace.workspace_id,
        FilesystemRunRepository(workspace),
        repository,
        index,
        index,
        fault_injector,
    )


def open_evaluation_workspace(
    root: Path, fault_injector: FaultInjector | None = None
) -> EvaluationService:
    store = WorkspaceStore()
    workspace = store.open(root)
    artifacts = FilesystemArtifactRepository(workspace, store)
    index = SQLiteArtifactIndex(workspace.index_path)
    return EvaluationService(
        workspace.workspace_id,
        FilesystemEvaluationSuiteRepository(workspace.root),
        FilesystemProtocolRepository(workspace.root),
        FilesystemRunRepository(workspace),
        artifacts,
        index,
        CandidateCatalog(DeterministicMockGateway()),
        fault_injector,
    )


def open_run_for_id(
    root: Path, run_id: str
) -> (
    RunService
    | ResearchService
    | ProjectService
    | LearningService
    | CrossflowService
    | EvaluationService
):
    workspace = WorkspaceStore().open(root)
    manifest = FilesystemRunRepository(workspace).read_manifest(run_id)
    workflow = manifest.get("workflow")
    if isinstance(workflow, dict) and workflow.get("name") == "research.compile-plain-text":
        return open_research_workspace(root)
    if isinstance(workflow, dict) and str(workflow.get("name", "")).startswith("project."):
        return open_project_workspace(root)
    if isinstance(workflow, dict) and str(workflow.get("name", "")).startswith("learning."):
        return open_learning_workspace(root)
    if isinstance(workflow, dict) and workflow.get("name") == "crossflow.bridge":
        return open_crossflow_workspace(root)
    if isinstance(workflow, dict) and workflow.get("name") == "system.evaluate-model-route":
        return open_evaluation_workspace(root)
    return open_run_workspace(root)


@contextmanager
def mutation_lock(root: Path, command: str) -> Iterator[None]:
    """Acquire only at bootstrap so CLI/application remain adapter-independent."""
    workspace = WorkspaceStore().open(root)
    with WorkspaceLock(workspace.locks_root / "workspace.lock", command):
        yield
