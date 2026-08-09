from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from peos.bootstrap import open_project_workspace, open_workspace
from peos.domain.errors import ProjectScopeViolation
from tests.project_support import project_workspace


def test_project_compile_resume_cache_packet_and_result_scope(tmp_path: Path) -> None:
    workspace, target, request = project_workspace(tmp_path)
    service = open_project_workspace(workspace)
    stopped = service.start(request, "snapshot-project-inputs")
    assert stopped["committed_steps"] == 1
    run_id = str(stopped["run_id"])
    completed = service.resume(run_id)
    assert completed["state"] == "SUCCEEDED"
    assert service.verify(run_id)["valid"] is True
    outputs = cast(dict[str, Any], completed["outputs"])
    refs = cast(list[dict[str, Any]], outputs["artifacts"])
    artifacts, _ = open_workspace(workspace)
    stored = [artifacts.get(item["artifact_id"]) for item in refs]
    assert {item.artifact.type for item in stored} == {
        "project.map",
        "project.charter",
        "project.codex_packet",
    }
    packet = next(item for item in stored if item.artifact.type == "project.codex_packet")
    packet_payload = cast(dict[str, Any], packet.artifact.payload)
    assert "README.md" not in packet_payload["allowed_paths"]
    assert "The verification command has not been executed by PEOS." in packet.artifact.body
    equivalent = service.start(request)
    assert equivalent["cache_hit"] is True
    assert equivalent["provider_calls"] == 0
    bad = {
        "schema_version": 1,
        "packet_artifact_id": packet.artifact.id,
        "packet_revision": packet.artifact.content_hash,
        "current_map_artifact_id": packet_payload["map_ref"]["id"],
        "current_map_revision": packet_payload["map_ref"]["revision"],
        "changed_files": [{"path": "README.md", "sha256": "sha256:" + "0" * 64}],
        "verification": {
            "cwd": ".",
            "argv": ["python", "-m", "pytest", "-q"],
            "exit_code": 0,
            "stdout_sha256": "sha256:" + "0" * 64,
            "stderr_sha256": "sha256:" + "0" * 64,
            "reported_by": "codex",
        },
    }
    bad_path = tmp_path / "bad-result.json"
    bad_path.write_text(json.dumps(bad))
    with pytest.raises(ProjectScopeViolation):
        service.accept_result(packet.artifact.id, bad_path)
    (target / "src" / "app.py").write_text("def status():\n    return 'healthy'\n")
    raw = (target / "src" / "app.py").read_bytes()
    import hashlib

    good = {
        **bad,
        "changed_files": [
            {"path": "src/app.py", "sha256": "sha256:" + hashlib.sha256(raw).hexdigest()}
        ],
    }
    good_path = tmp_path / "good-result.json"
    good_path.write_text(json.dumps(good))
    accepted = service.accept_result(packet.artifact.id, good_path)
    assert accepted["reported_verification"] is True
    assert service.verify(str(accepted["run_id"]))["valid"] is True
    old = artifacts.get(str(accepted["previous_map_id"]))
    new = artifacts.get(str(accepted["updated_map_id"]))
    assert old.artifact.id != new.artifact.id
    new_payload = cast(dict[str, Any], new.artifact.payload)
    assert new_payload["accepted_result"]["verification_provenance"] == "reported"
