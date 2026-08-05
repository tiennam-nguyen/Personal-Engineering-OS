from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.adapters.filesystem.workspace_lock import WorkspaceLock


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "peos.cli.main", "--workspace", str(root), *args],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def _workspace(root: Path) -> str:
    assert _run(root, "init").returncode == 0
    created = _run(root, "artifact", "create", "--title", "Source", "--body", "Body")
    assert created.returncode == 0
    return str(json.loads(created.stdout)["id"])


def _stopped(root: Path) -> tuple[str, str]:
    source = _workspace(root)
    result = _run(
        root,
        "run",
        "start",
        "sample.derive-concept",
        "--input",
        source,
        "--stop-after-step",
        "prepare-derived-concept",
    )
    assert result.returncode == 0
    return source, str(json.loads(result.stdout)["run_id"])


def _events(root: Path, run_id: str) -> list[dict[str, object]]:
    path = root / ".peos" / "runs" / run_id / "events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_cli_run_full_workflow(tmp_path: Path) -> None:
    source = _workspace(tmp_path)
    result = _run(tmp_path, "run", "start", "sample.derive-concept", "--input", source)
    assert result.returncode == 0
    assert json.loads(result.stdout)["state"] == "SUCCEEDED"


def test_cli_run_stop_inspect_resume(tmp_path: Path) -> None:
    _, run_id = _stopped(tmp_path)
    assert json.loads(_run(tmp_path, "run", "inspect", run_id).stdout)["state"] == "RUNNING"
    assert json.loads(_run(tmp_path, "run", "resume", run_id).stdout)["state"] == "SUCCEEDED"


def test_cli_resume_does_not_repeat_first_step(tmp_path: Path) -> None:
    _, run_id = _stopped(tmp_path)
    manifest = json.loads((tmp_path / ".peos" / "runs" / run_id / "manifest.json").read_text())
    step_id = manifest["steps"][0]["step_id"]

    def count() -> int:
        return sum(
            event["type"] == "step.execution_started" and event["step_id"] == step_id
            for event in _events(tmp_path, run_id)
        )

    assert count() == 1
    assert _run(tmp_path, "run", "resume", run_id).returncode == 0
    assert count() == 1


def test_cli_run_verify(tmp_path: Path) -> None:
    _, run_id = _stopped(tmp_path)
    result = _run(tmp_path, "run", "verify", run_id)
    assert result.returncode == 0 and json.loads(result.stdout)["valid"] is True


def test_cli_run_cancel(tmp_path: Path) -> None:
    _, run_id = _stopped(tmp_path)
    result = _run(tmp_path, "run", "cancel", run_id)
    assert result.returncode == 0 and json.loads(result.stdout)["state"] == "CANCELLED"


def test_cli_cancelled_run_cannot_resume(tmp_path: Path) -> None:
    _, run_id = _stopped(tmp_path)
    assert _run(tmp_path, "run", "cancel", run_id).returncode == 0
    result = _run(tmp_path, "run", "resume", run_id)
    assert result.returncode == 4 and "Traceback" not in result.stderr


def test_cli_unknown_run_is_safe(tmp_path: Path) -> None:
    _workspace(tmp_path)
    result = _run(tmp_path, "run", "inspect", "run_" + "f" * 32)
    assert result.returncode == 3 and result.stdout == "" and "Traceback" not in result.stderr


def test_cli_journal_corruption_is_safe(tmp_path: Path) -> None:
    _, run_id = _stopped(tmp_path)
    path = tmp_path / ".peos" / "runs" / run_id / "events.jsonl"
    path.write_text(path.read_text(encoding="utf-8") + "{", encoding="utf-8")
    result = _run(tmp_path, "run", "verify", run_id)
    assert result.returncode == 4 and result.stdout == "" and "Traceback" not in result.stderr


def test_cli_workspace_locked_is_safe(tmp_path: Path) -> None:
    source = _workspace(tmp_path)
    workspace = WorkspaceStore().open(tmp_path)
    with WorkspaceLock(workspace.locks_root / "workspace.lock", "test holder"):
        result = _run(tmp_path, "run", "start", "sample.derive-concept", "--input", source)
    assert result.returncode == 5 and "Traceback" not in result.stderr


@pytest.mark.parametrize("command", [("run", "inspect", "bad"), ("run", "verify", "bad")])
def test_cli_expected_run_errors_have_no_traceback(
    tmp_path: Path, command: tuple[str, ...]
) -> None:
    _workspace(tmp_path)
    result = _run(tmp_path, *command)
    assert result.returncode != 0 and "Traceback" not in result.stderr


def test_cli_outputs_parse_as_json(tmp_path: Path) -> None:
    _, run_id = _stopped(tmp_path)
    for command in (("run", "inspect", run_id), ("run", "verify", run_id)):
        result = _run(tmp_path, *command)
        assert result.returncode == 0
        json.loads(result.stdout)
