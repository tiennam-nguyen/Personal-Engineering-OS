from pathlib import Path
from typing import cast

from peos.bootstrap import open_research_workspace
from tests.research_support import research_workspace


def test_resume_after_ingestion_succeeds_without_inbox(tmp_path: Path) -> None:
    root, sources = research_workspace(tmp_path)
    stopped = open_research_workspace(root).start(
        "Is it effective?", sources, "ingest-research-inputs"
    )
    run_id = cast(str, stopped["run_id"])
    events = open_research_workspace(root)._runs.events(run_id)
    before = sum(event.type == "step.execution_started" for event in events)
    object_bytes = {
        path: path.read_bytes()
        for path in (root / ".peos" / "objects").glob("**/*")
        if path.is_file()
    }
    for source in sources:
        (root / source).unlink()
    resumed = open_research_workspace(root).resume(run_id)
    after = sum(
        event.type == "step.execution_started"
        for event in open_research_workspace(root)._runs.events(run_id)
    )
    assert resumed["state"] == "SUCCEEDED" and before == 1 and after == 3
    assert all(path.read_bytes() == raw for path, raw in object_bytes.items())
