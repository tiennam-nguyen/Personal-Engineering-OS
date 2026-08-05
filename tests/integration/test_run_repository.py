from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from peos.adapters.filesystem.workspace import Workspace, WorkspaceStore
from peos.adapters.filesystem.workspace_lock import WorkspaceLock
from peos.application.runs import RunService
from peos.bootstrap import initialize_workspace, open_run_workspace
from peos.domain.errors import WorkspaceLockedError


def _holder(workspace: Path, ready: Path) -> subprocess.Popen[str]:
    script = (
        "import time\n"
        "from pathlib import Path\n"
        "from peos.adapters.filesystem.workspace import WorkspaceStore\n"
        "from peos.adapters.filesystem.workspace_lock import WorkspaceLock\n"
        f"root=Path({str(workspace)!r})\n"
        f"ready=Path({str(ready)!r})\n"
        "ws=WorkspaceStore().open(root)\n"
        "with WorkspaceLock(ws.locks_root/'workspace.lock','holder'):\n"
        " ready.write_text('ready',encoding='utf-8')\n"
        " time.sleep(30)\n"
    )
    return subprocess.Popen([sys.executable, "-c", script], text=True)


def _wait_ready(ready: Path) -> None:
    deadline = time.monotonic() + 10
    while not ready.exists():
        if time.monotonic() >= deadline:
            raise AssertionError("lock holder did not signal readiness")
        time.sleep(0.05)


def test_workspace_lock_blocks_second_mutator(tmp_path: Path) -> None:
    initialize_workspace(tmp_path)
    ready = tmp_path / "ready"
    holder = _holder(tmp_path, ready)
    try:
        _wait_ready(ready)
        workspace = WorkspaceStore().open(tmp_path)
        with pytest.raises(WorkspaceLockedError):
            with WorkspaceLock(workspace.locks_root / "workspace.lock", "contender"):
                raise AssertionError("contender acquired held lock")
    finally:
        holder.terminate()
        holder.wait(timeout=10)


def test_workspace_lock_releases_after_context_exit(tmp_path: Path) -> None:
    initialize_workspace(tmp_path)
    workspace = WorkspaceStore().open(tmp_path)
    path = workspace.locks_root / "workspace.lock"
    with WorkspaceLock(path, "first"):
        pass
    with WorkspaceLock(path, "second"):
        assert path.exists()


def test_process_death_releases_workspace_lock(tmp_path: Path) -> None:
    initialize_workspace(tmp_path)
    ready = tmp_path / "ready"
    holder = _holder(tmp_path, ready)
    _wait_ready(ready)
    holder.kill()
    holder.wait(timeout=10)
    workspace = WorkspaceStore().open(tmp_path)
    with WorkspaceLock(workspace.locks_root / "workspace.lock", "after-death"):
        pass


def _stopped(tmp_path: Path) -> tuple[str, RunService, Workspace]:
    artifacts, _, _, _ = initialize_workspace(tmp_path)
    source = artifacts.create_concept("Source", "Body", [])
    service = open_run_workspace(tmp_path)
    run_id = str(
        service.start("sample.derive-concept", source.artifact.id, "prepare-derived-concept")[
            "run_id"
        ]
    )
    return run_id, service, WorkspaceStore().open(tmp_path)


def test_read_only_inspect_does_not_require_mutation_lock(tmp_path: Path) -> None:
    run_id, service, workspace = _stopped(tmp_path)
    with WorkspaceLock(workspace.locks_root / "workspace.lock", "holder"):
        assert service.inspect(run_id)["state"] == "RUNNING"


def test_read_only_verify_does_not_require_mutation_lock(tmp_path: Path) -> None:
    run_id, service, workspace = _stopped(tmp_path)
    with WorkspaceLock(workspace.locks_root / "workspace.lock", "holder"):
        assert service.verify(run_id)["valid"] is True
