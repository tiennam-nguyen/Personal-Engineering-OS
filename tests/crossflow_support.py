from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from peos.bootstrap import (
    initialize_workspace,
    open_learning_workspace,
    open_project_workspace,
    open_research_workspace,
    open_workspace,
)
from peos.domain.artifacts.model import StoredArtifact
from tests.project_support import PROTOCOL as PROJECT_PROTOCOL
from tests.research_support import PROTOCOL as RESEARCH_PROTOCOL


def source_workspace(
    tmp_path: Path,
) -> tuple[Path, StoredArtifact, StoredArtifact, StoredArtifact, StoredArtifact]:
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    _protocols(workspace)
    source = workspace / "inbox" / "bounded.txt"
    source.write_text("Bounded retries reduce uncontrolled repeated execution.\n")
    research = open_research_workspace(workspace).start(
        "Do bounded retries reduce repeated execution?", ["inbox/bounded.txt"]
    )
    research_refs = cast(list[dict[str, Any]], research["produced_artifacts"])
    artifacts, _ = open_workspace(workspace)
    claim = next(
        artifacts.get(str(item["id"]))
        for item in research_refs
        if artifacts.get(str(item["id"])).artifact.type == "research.claim"
    )

    target = tmp_path / "fixture-repo"
    (target / "src").mkdir(parents=True)
    (target / "tests").mkdir()
    (target / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0.1.0'\n")
    (target / "src" / "app.py").write_text("def status():\n    return 'ok'\n")
    (target / "tests" / "test_app.py").write_text("def test_status():\n    assert True\n")
    request = tmp_path / "project.json"
    request.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_slug": "crossflow-fixture",
                "request": "Preserve bounded deterministic execution.",
                "stakeholder": "Local developer",
                "intolerable_failure": "Unbounded repeated execution.",
                "constraints": ["no runtime dependency"],
                "definition_of_done": "Fixture verification passes.",
                "deadline": None,
                "repository": {
                    "mode": "existing_repository",
                    "root": str(target),
                    "reads": [
                        {
                            "path": "pyproject.toml",
                            "role": "manifest",
                            "question": "What toolchain?",
                        },
                        {
                            "path": "src/app.py",
                            "role": "entrypoint",
                            "question": "Where is behavior?",
                        },
                        {
                            "path": "tests/test_app.py",
                            "role": "test",
                            "question": "What verifies it?",
                        },
                    ],
                    "flow_paths": ["src/app.py", "tests/test_app.py"],
                    "candidate_change_paths": ["src/app.py", "tests/test_app.py"],
                    "forbidden_change_paths": ["README.md"],
                },
                "verification": {
                    "cwd": ".",
                    "argv": ["python", "-m", "pytest", "-q"],
                    "expected_exit_code": 0,
                    "expected_evidence": "fixture tests pass",
                },
                "research_synthesis_id": None,
                "sensitivity": "private",
            }
        )
    )
    project = open_project_workspace(workspace).start(request)
    project_refs = cast(list[dict[str, Any]], cast(dict[str, Any], project["outputs"])["artifacts"])
    charter = artifacts.get(str(project_refs[1]["artifact_id"]))
    packet = artifacts.get(str(project_refs[2]["artifact_id"]))

    goal, diagnostic = _learning_inputs(tmp_path)
    learning = open_learning_workspace(workspace).start_compile(goal, diagnostic)
    learning_refs = cast(
        list[dict[str, Any]], cast(dict[str, Any], learning["outputs"])["artifacts"]
    )
    learning_goal = artifacts.get(str(learning_refs[0]["artifact_id"]))
    return workspace, claim, charter, packet, learning_goal


def requests(
    tmp_path: Path,
    claim: StoredArtifact,
    charter: StoredArtifact,
    packet: StoredArtifact,
    goal: StoredArtifact,
) -> tuple[Path, Path, Path]:
    verification = cast(dict[str, Any], packet.artifact.payload)["verification"]
    values = [
        {
            "schema_version": 1,
            "kind": "project_failure_to_learning_exercise",
            "project_packet_id": packet.artifact.id,
            "project_packet_revision": packet.artifact.content_hash,
            "failure": {
                "verification_cwd": verification["cwd"],
                "verification_argv": verification["argv"],
                "expected_exit_code": verification["expected_exit_code"],
                "reported_exit_code": 1,
                "failed_check": "test_status",
                "expected_behavior": "status is ok",
                "observed_behavior": "status was failed",
                "reported_by": "user",
            },
            "learning_target": {
                "concept_id": "bounded-verification",
                "concept_title": "Bounded verification",
                "estimated_minutes": 5,
            },
        },
        {
            "schema_version": 1,
            "kind": "research_claim_to_project_adr",
            "research_claim_id": claim.artifact.id,
            "research_claim_revision": claim.artifact.content_hash,
            "project_charter_id": charter.artifact.id,
            "project_charter_revision": charter.artifact.content_hash,
            "adr": {
                "decision_key": "bounded-retries",
                "context": "Repeated execution must be bounded.",
                "decision": "Use bounded retries.",
                "alternatives": ["Unbounded retries", "No retry"],
                "consequences": ["Failures terminate predictably"],
                "falsifier": "Evidence shows bounded retries increase uncontrolled execution.",
            },
        },
        {
            "schema_version": 1,
            "kind": "learning_gap_to_research_question",
            "learning_goal_id": goal.artifact.id,
            "learning_goal_revision": goal.artifact.content_hash,
            "gap_concept_id": "binary-search-interval",
        },
    ]
    paths = []
    for index, value in enumerate(values):
        path = tmp_path / f"bridge-{index}.json"
        path.write_text(json.dumps(value))
        paths.append(path)
    return paths[0], paths[1], paths[2]


def _protocols(workspace: Path) -> None:
    entries = []
    for name, protocol, task, output in (
        (
            "research.claim-extraction",
            RESEARCH_PROTOCOL,
            "claim_extraction",
            "research.candidate_claim_set.v1",
        ),
        (
            "project.plan-compilation",
            PROJECT_PROTOCOL,
            "project_planning",
            "project.charter_draft.v1",
        ),
    ):
        directory = workspace / "protocols" / name
        directory.mkdir(parents=True)
        (directory / "1.0.0.md").write_text(protocol, newline="")
        digest = "sha256:" + hashlib.sha256(protocol.encode()).hexdigest()
        entries.append(
            f"  - name: {name}\n"
            "    version: 1.0.0\n"
            f"    path: protocols/{name}/1.0.0.md\n"
            f"    sha256: {digest}\n"
            f"    task_kinds: [{task}]\n"
            f"    output_contracts: [{output}]\n"
            "    sensitivity_ceiling: private\n"
            "    status: active"
        )
    (workspace / "protocols" / "registry.yaml").write_text(
        "schema_version: 1\nprotocols:\n" + "\n".join(entries) + "\n", newline=""
    )


def _learning_inputs(tmp_path: Path) -> tuple[Path, Path]:
    from tests.learning_support import learning_workspace

    _, goal, diagnostic = learning_workspace(tmp_path / "learning-fixture")
    return goal, diagnostic
