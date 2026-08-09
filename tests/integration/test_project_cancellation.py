from __future__ import annotations

from pathlib import Path

import pytest

from peos.bootstrap import open_project_workspace
from peos.domain.errors import RunConflictError
from tests.project_support import project_workspace


def test_project_cancellation_preserves_snapshot_and_is_idempotent(tmp_path: Path) -> None:
    workspace, _, request = project_workspace(tmp_path)
    service = open_project_workspace(workspace)
    stopped = service.start(request, "snapshot-project-inputs")
    run_id = str(stopped["run_id"])
    first = service.cancel(run_id)
    second = service.cancel(run_id)
    assert first["state"] == second["state"] == "CANCELLED"
    assert service.verify(run_id)["valid"] is True
    with pytest.raises(RunConflictError):
        service.resume(run_id)
