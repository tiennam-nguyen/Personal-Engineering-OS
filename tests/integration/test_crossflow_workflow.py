from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from peos.bootstrap import open_crossflow_workspace, open_graph_workspace, open_workspace
from tests.crossflow_support import requests, source_workspace


def test_three_crossflow_bridges_are_reversible_and_rebuildable(tmp_path: Path) -> None:
    workspace, claim, charter, packet, goal = source_workspace(tmp_path)
    request_paths = requests(tmp_path, claim, charter, packet, goal)
    source_bytes = {
        item.artifact.id: (workspace / item.canonical_path).read_bytes()
        for item in (claim, charter, packet, goal)
    }
    service = open_crossflow_workspace(workspace)
    runs = [service.start(path) for path in request_paths]
    assert [item["operation"] for item in runs] == [
        "project_failure_to_learning_exercise",
        "research_claim_to_project_adr",
        "learning_gap_to_research_question",
    ]
    assert all(service.verify(str(item["run_id"]))["valid"] is True for item in runs)
    artifacts, indexing = open_workspace(workspace)
    targets = [
        artifacts.get(str(cast(dict[str, Any], run["outputs"])["artifacts"][0]["artifact_id"]))
        for run in runs
    ]
    assert [item.artifact.type for item in targets] == [
        "learning.exercise",
        "project.adr",
        "research.question",
    ]
    expected = {
        (targets[0].artifact.id, "derived_from", packet.artifact.id),
        (claim.artifact.id, "supports", targets[1].artifact.id),
        (targets[1].artifact.id, "references", charter.artifact.id),
        (targets[2].artifact.id, "derived_from", goal.artifact.id),
    }
    graph = open_graph_workspace(workspace)
    for source, relation, target in expected:
        edge = {"source_artifact_id": source, "relation": relation, "target_artifact_id": target}
        assert edge in cast(list[dict[str, object]], graph.traverse(source)["edges"])
        assert edge in cast(list[dict[str, object]], graph.traverse(target)["edges"])
    depth_two = graph.traverse(claim.artifact.id, 2)
    assert {
        node["artifact_id"]: node["distance"]
        for node in cast(list[dict[str, object]], depth_two["nodes"])
    }[charter.artifact.id] == 2
    assert all(
        (workspace / item.canonical_path).read_bytes() == source_bytes[item.artifact.id]
        for item in (claim, charter, packet, goal)
    )
    before = {
        tuple(edge.values())
        for endpoint in (claim.artifact.id, packet.artifact.id, goal.artifact.id)
        for edge in cast(list[dict[str, object]], graph.traverse(endpoint, 2)["edges"])
    }
    (workspace / ".peos" / "index.sqlite3").unlink()
    assert indexing.rebuild() == 11
    after_graph = open_graph_workspace(workspace)
    after = {
        tuple(edge.values())
        for endpoint in (claim.artifact.id, packet.artifact.id, goal.artifact.id)
        for edge in cast(list[dict[str, object]], after_graph.traverse(endpoint, 2)["edges"])
    }
    assert before == after
    assert all(service.verify(str(item["run_id"]))["valid"] is True for item in runs)
