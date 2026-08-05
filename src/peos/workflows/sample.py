"""The single sample workflow's pure construction and verifier."""

from __future__ import annotations

import hashlib

from peos.domain.artifacts.model import Artifact, Author, Provenance
from peos.domain.artifacts.validation import validate_artifact
from peos.domain.runs.model import canonical_json
from peos.domain.workflows.model import StepDefinition, WorkflowDefinition

WORKFLOW = WorkflowDefinition(
    "sample.derive-concept",
    "1.0.0",
    (
        StepDefinition(1, "prepare-derived-concept", "1.0.0", "PURE"),
        StepDefinition(2, "commit-derived-concept", "1.0.0", "REVERSIBLE_WRITE"),
    ),
)


def prepare(input_artifact: Artifact, run_id: str, created_at: str) -> Artifact:
    identifier = (
        "art_"
        + hashlib.sha256(
            f"{run_id}:sample.derive-concept:1.0.0:commit-derived-concept".encode()
        ).hexdigest()[:32]
    )
    tags = list(input_artifact.tags)
    for tag in ("workflow-derived", "sample-workflow"):
        if tag not in tags:
            tags.append(tag)
    artifact = Artifact(
        id=identifier,
        type="knowledge.concept",
        schema_version=1,
        title=f"Derived: {input_artifact.title}",
        status="draft",
        workspace_id=input_artifact.workspace_id,
        created_at=created_at,
        updated_at=created_at,
        authors=(Author("system", "peos"),),
        sensitivity=input_artifact.sensitivity,
        tags=tuple(tags),
        links=(),
        provenance=Provenance(
            "system",
            run_id,
            ({"artifact_id": input_artifact.id, "content_hash": input_artifact.content_hash},),
        ),
        content_hash=None,
        body=(
            f"Derived deterministically from artifact {input_artifact.id} "
            f"at {input_artifact.content_hash}.\n\n{input_artifact.body}"
        ),
    )
    return validate_artifact(
        artifact, expected_workspace_id=input_artifact.workspace_id, require_hash=False
    )


def artifact_data(artifact: Artifact) -> dict[str, object]:
    return {
        "id": artifact.id,
        "type": artifact.type,
        "schema_version": artifact.schema_version,
        "title": artifact.title,
        "status": artifact.status,
        "workspace_id": artifact.workspace_id,
        "created_at": artifact.created_at,
        "updated_at": artifact.updated_at,
        "authors": [{"kind": a.kind, "id": a.id} for a in artifact.authors],
        "sensitivity": artifact.sensitivity,
        "tags": list(artifact.tags),
        "links": list(artifact.links),
        "provenance": {
            "producer": artifact.provenance.producer,
            "run_id": artifact.provenance.run_id,
            "source_refs": list(artifact.provenance.source_refs),
        },
        "body": artifact.body,
    }


def verify_prepared(
    input_artifact: Artifact, run_id: str, created_at: str, data: dict[str, object]
) -> Artifact:
    expected = artifact_data(prepare(input_artifact, run_id, created_at))
    if canonical_json(expected) != canonical_json(data):
        raise ValueError("Prepared artifact is not deterministic.")
    return prepare(input_artifact, run_id, created_at)
