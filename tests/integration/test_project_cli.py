from __future__ import annotations

import json
from pathlib import Path

import pytest

from peos.cli.main import main
from tests.project_support import project_workspace


def test_project_cli_compile_export_verify_and_no_cache(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace, _, request = project_workspace(tmp_path)
    argv = ["--workspace", str(workspace), "project", "compile", "--request-file", str(request)]
    assert main(argv) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "SUCCEEDED"
    run_id = result["run_id"]
    packet_id = result["outputs"]["artifacts"][2]["artifact_id"]
    assert main(["--workspace", str(workspace), "run", "verify", run_id]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert main(["--workspace", str(workspace), "project", "export-codex", packet_id]) == 0
    exported = json.loads(capsys.readouterr().out)
    assert exported["content"].startswith("# Codex Milestone Packet\n")
    assert main([*argv, "--no-cache"]) == 0
    bypass = json.loads(capsys.readouterr().out)
    assert bypass["cache_hit"] is False
    assert bypass["provider_calls"] == 1


def test_project_cli_expected_error_has_no_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace, _, request = project_workspace(tmp_path)
    data = json.loads(request.read_text())
    data["repository"]["reads"][0]["path"] = "../escape"
    request.write_text(json.dumps(data))
    argv = ["--workspace", str(workspace), "project", "compile", "--request-file", str(request)]
    assert main(argv) != 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Traceback" not in captured.err
