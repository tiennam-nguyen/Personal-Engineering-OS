import json
from pathlib import Path

import pytest

from peos.cli.main import main
from tests.research_support import research_workspace


def test_cli_full_stop_resume_verify_and_safe_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, sources = research_workspace(tmp_path)
    args = ["--workspace", str(root), "research", "compile", "--question", "Is it effective?"]
    for source in sources:
        args.extend(["--source", source])
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "SUCCEEDED" and result["unreadable_segments"] == 1
    assert main(["--workspace", str(root), "run", "verify", result["run_id"]]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert (
        main(
            [
                "--workspace",
                str(root),
                "research",
                "compile",
                "--question",
                "Q",
                "--source",
                "../escape.txt",
            ]
        )
        != 0
    )
    assert "Traceback" not in capsys.readouterr().err
