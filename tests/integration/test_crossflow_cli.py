from __future__ import annotations

import json
from pathlib import Path

import pytest

from peos.cli.main import main
from tests.crossflow_support import requests, source_workspace


def test_crossflow_and_graph_cli_json_and_safe_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace, claim, charter, packet, goal = source_workspace(tmp_path)
    exercise_request, _, _ = requests(tmp_path, claim, charter, packet, goal)
    assert (
        main(
            [
                "--workspace",
                str(workspace),
                "crossflow",
                "bridge",
                "--request-file",
                str(exercise_request),
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    target = result["outputs"]["artifacts"][0]["artifact_id"]
    assert main(["--workspace", str(workspace), "graph", packet.artifact.id, "--depth", "1"]) == 0
    graph = json.loads(capsys.readouterr().out)
    assert {packet.artifact.id, target} <= {node["artifact_id"] for node in graph["nodes"]}
    assert main(["--workspace", str(workspace), "graph", packet.artifact.id, "--depth", "-1"]) == 4
    error = capsys.readouterr().err
    assert "graph_projection_divergence" in error and "Traceback" not in error
