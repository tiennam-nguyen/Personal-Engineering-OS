from pathlib import Path
from typing import cast

import pytest

from peos.bootstrap import open_research_workspace
from peos.domain.errors import RunConflictError
from tests.research_support import research_workspace


def test_cancel_after_ingestion_preserves_and_is_idempotent(tmp_path: Path) -> None:
    root, sources = research_workspace(tmp_path)
    stopped = open_research_workspace(root).start("Question?", sources, "ingest-research-inputs")
    run_id = cast(str, stopped["run_id"])
    service = open_research_workspace(root)
    cancelled = service.cancel(run_id)
    count = len(service._runs.events(run_id))
    assert cancelled["state"] == "CANCELLED"
    assert len(service._runs.events(run_id)) == count
    assert service.cancel(run_id)["state"] == "CANCELLED"
    assert len(service._runs.events(run_id)) == count
    assert service.verify(run_id)["valid"] is True
    with pytest.raises(RunConflictError):
        service.resume(run_id)
