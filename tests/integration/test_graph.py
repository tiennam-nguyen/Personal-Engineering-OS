from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from peos.adapters.filesystem.repository import FilesystemArtifactRepository
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.adapters.filesystem.workspace_lock import WorkspaceLock
from peos.adapters.sqlite.artifact_index import SQLiteArtifactIndex
from peos.bootstrap import initialize_workspace, open_graph_workspace
from peos.domain.artifacts.model import Artifact, Author, Provenance
from peos.domain.errors import GraphProjectionDivergence


def _artifact(identifier: str, target: str) -> Artifact:
    return Artifact(
        identifier,
        "knowledge.concept",
        1,
        identifier,
        "draft",
        "ws_" + "1" * 32,
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00Z",
        (Author("human", "user"),),
        "private",
        (),
        ({"rel": "references", "target": target},),
        Provenance("human", None, ()),
        None,
        "Cycle fixture\n",
    )


def test_graph_depth_cycle_order_projection_verification_and_read_only_lock(tmp_path: Path) -> None:
    workspace_path = tmp_path / "workspace"
    _, indexing, workspace_id, _ = initialize_workspace(workspace_path)
    a, b = "art_" + "a" * 32, "art_" + "b" * 32
    workspace = WorkspaceStore().open(workspace_path)
    repository = FilesystemArtifactRepository(workspace, WorkspaceStore())
    repository.save(replace(_artifact(a, b), workspace_id=workspace_id))
    repository.save(replace(_artifact(b, a), workspace_id=workspace_id))
    assert indexing.rebuild() == 2
    graph = open_graph_workspace(workspace_path)
    assert graph.traverse(a, 0)["edges"] == []
    result = graph.traverse(a, 5)
    assert [node["artifact_id"] for node in cast(list[dict[str, object]], result["nodes"])] == [
        a,
        b,
    ]
    assert result["edges"] == [
        {"source_artifact_id": a, "relation": "references", "target_artifact_id": b},
        {"source_artifact_id": b, "relation": "references", "target_artifact_id": a},
    ]
    with WorkspaceLock(workspace.locks_root / "workspace.lock", "held by test"):
        assert open_graph_workspace(workspace_path).traverse(a, 1)["root_artifact_id"] == a
    connection = sqlite3.connect(workspace.index_path)
    connection.execute("UPDATE relation SET host_revision = ?", ("sha256:" + "0" * 64,))
    connection.commit()
    connection.close()
    with pytest.raises(GraphProjectionDivergence):
        graph.traverse(a, 1)
    with pytest.raises(GraphProjectionDivergence):
        graph.traverse(a, -1)


def test_relation_projection_records_host_and_rebuilds_exact_edges(tmp_path: Path) -> None:
    workspace_path = tmp_path / "workspace"
    _, indexing, workspace_id, _ = initialize_workspace(workspace_path)
    a, b = "art_" + "a" * 32, "art_" + "b" * 32
    workspace = WorkspaceStore().open(workspace_path)
    repository = FilesystemArtifactRepository(workspace, WorkspaceStore())
    first = repository.save(replace(_artifact(a, b), workspace_id=workspace_id))
    repository.save(replace(_artifact(b, a), workspace_id=workspace_id, links=()))
    assert indexing.rebuild() == 2
    rows = SQLiteArtifactIndex(workspace.index_path).outgoing(a)
    assert len(rows) == 1
    assert rows[0].host_artifact_id == a
    assert rows[0].host_revision == first.artifact.content_hash
