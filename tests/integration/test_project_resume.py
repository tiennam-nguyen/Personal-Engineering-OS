from __future__ import annotations

from pathlib import Path

from peos.bootstrap import open_project_workspace
from tests.project_support import project_workspace


def test_resume_after_model_step_does_not_call_gateway_again(tmp_path: Path) -> None:
    workspace, _, request = project_workspace(tmp_path)
    service = open_project_workspace(workspace)
    stopped = service.start(request, "draft-project-charter")
    assert stopped["provider_calls"] == 1
    run_id = str(stopped["run_id"])
    resumed = service.resume(run_id)
    assert resumed["provider_calls"] == 1
    assert resumed["committed_steps"] == 3
