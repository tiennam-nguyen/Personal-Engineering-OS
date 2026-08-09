from __future__ import annotations

import json
from pathlib import Path

import pytest

from peos.cli.main import main
from tests.integration.test_evaluation_workflow import workspace


def test_eval_run_failed_qualification_and_compare_are_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = workspace(tmp_path)
    common = [
        "--workspace",
        str(root),
        "eval",
        "run",
        "model.summarization.core",
        "--provider",
        "mock",
    ]
    assert (
        main([*common, "--model", "deterministic-concept-summary-v1", "--model-revision", "1"]) == 0
    )
    qualified = json.loads(capsys.readouterr().out)
    assert qualified["status"] == "QUALIFIED"
    assert (
        main(
            [*common, "--model", "deterministic-concept-summary-short-v1", "--model-revision", "1"]
        )
        == 0
    )
    failed = json.loads(capsys.readouterr().out)
    assert failed["status"] == "FAILED"
    assert (
        main(
            [
                "--workspace",
                str(root),
                "eval",
                "compare",
                qualified["eval_run_id"],
                failed["eval_run_id"],
            ]
        )
        == 0
    )
    comparison = json.loads(capsys.readouterr().out)
    assert len(comparison["candidates"]) == 2
    assert "overall_winner" not in comparison


def test_eval_cli_expected_error_has_no_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = workspace(tmp_path)
    code = main(
        [
            "--workspace",
            str(root),
            "eval",
            "run",
            "missing",
            "--provider",
            "mock",
            "--model",
            "missing",
            "--model-revision",
            "1",
        ]
    )
    captured = capsys.readouterr()
    assert code != 0 and "Traceback" not in captured.err and captured.out == ""
