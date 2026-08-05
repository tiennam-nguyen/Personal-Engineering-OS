from pathlib import Path
from typing import cast

from peos.bootstrap import open_research_workspace
from tests.research_support import research_workspace


def test_acceptance_fixture_claims_contradiction_unreadable_and_verify(tmp_path: Path) -> None:
    root, sources = research_workspace(tmp_path)
    result = open_research_workspace(root).start("Is the treatment effective?", sources)
    assert result["state"] == "SUCCEEDED"
    assert result["unreadable_segments"] == 1
    assert len(cast(list[object], result["claim_ids"])) == 3
    assert len(cast(list[object], result["contradiction_ids"])) == 1
    run_id = cast(str, result["run_id"])
    plan = open_research_workspace(root)._runs.read_evidence(
        run_id, "research/normalized-research-map.json"
    )["data"]
    assert isinstance(plan, dict) and isinstance(plan["claims"], list)
    treatment = [
        item
        for item in plan["claims"]
        if isinstance(item, dict) and item["semantic_key"] == "the treatment is effective"
    ]
    assert sorted(len(item["evidence_refs"]) for item in treatment) == [1, 2]
    assert all(item["evidence_status"] == "CONTESTED" for item in treatment)
    assert open_research_workspace(root).verify(run_id)["valid"] is True


def test_equivalent_run_hits_cache_and_bypass_calls(tmp_path: Path) -> None:
    root, sources = research_workspace(tmp_path)
    first = open_research_workspace(root).start("Is the treatment effective?", sources)
    second = open_research_workspace(root).start("Is the treatment effective?", sources)
    assert first["provider_calls"] == 1
    assert second["cache_hit"] is True and second["provider_calls"] == 0
    third = open_research_workspace(root).start(
        "Is the treatment effective?", sources, no_cache=True
    )
    assert third["cache_hit"] is False and third["provider_calls"] == 1
