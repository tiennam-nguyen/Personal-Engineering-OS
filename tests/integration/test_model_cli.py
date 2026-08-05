import json
from pathlib import Path

import pytest

from peos.cli.main import main
from tests.integration.test_model_workflow import workspace


def test_protocol_and_model_cli_emit_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, source_id = workspace(tmp_path)
    assert main(["--workspace", str(root), "protocol", "list"]) == 0
    protocol_output = capsys.readouterr().out
    assert json.loads(protocol_output)[0]["name"] == "sample.concept-summary"
    assert (
        main(
            [
                "--workspace",
                str(root),
                "run",
                "start",
                "sample.mock-summarize-concept",
                "--input",
                source_id,
            ]
        )
        == 0
    )
    run_output = json.loads(capsys.readouterr().out)
    assert run_output["state"] == "SUCCEEDED"
    assert run_output["model_calls"][0]["provider_calls"] == 1
