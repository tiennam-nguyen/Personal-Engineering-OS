"""Pure artifact validation and normalization."""

from __future__ import annotations

import re
from datetime import datetime

from peos.domain.artifacts.model import Artifact, Author, Provenance
from peos.domain.errors import ValidationError

WORKSPACE_ID_PATTERN = re.compile(r"^ws_[0-9a-f]{32}$")
ARTIFACT_ID_PATTERN = re.compile(r"^art_[0-9a-f]{32}$")
CONTENT_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
ARTIFACT_TYPES = frozenset(
    {
        "knowledge.concept",
        "research.question",
        "research.source",
        "research.claim",
        "research.contradiction",
        "research.synthesis",
        "project.map",
        "project.charter",
        "project.codex_packet",
        "project.adr",
        "learning.goal",
        "learning.attempt",
        "learning.mastery",
        "learning.exercise",
    }
)
SCHEMA_VERSION = 1
_ENVELOPE_FIELDS = (
    "id",
    "type",
    "schema_version",
    "title",
    "status",
    "workspace_id",
    "created_at",
    "updated_at",
    "authors",
    "sensitivity",
    "tags",
    "links",
    "provenance",
    "integrity",
)
_STATUSES = frozenset({"draft", "reviewed", "accepted", "superseded", "rejected"})
_SENSITIVITIES = frozenset({"private", "confidential", "public"})


def normalize_body(body: str) -> str:
    normalized = body.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"
    if not normalized.strip():
        raise ValidationError("Artifact body must contain non-whitespace text.")
    return normalized


def normalize_tags(tags: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    result: list[str] = []
    for tag in tags:
        if not isinstance(tag, str) or not (trimmed := tag.strip()):
            raise ValidationError("Tags must be non-empty strings.")
        if trimmed not in result:
            result.append(trimmed)
    return tuple(result)


def validate_workspace_id(value: str) -> None:
    if not WORKSPACE_ID_PATTERN.fullmatch(value):
        raise ValidationError("Workspace ID has an invalid format.")


def validate_artifact_id(value: str) -> None:
    if not ARTIFACT_ID_PATTERN.fullmatch(value):
        raise ValidationError("Artifact ID has an invalid format.")


def _validate_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValidationError("Timestamp is not ISO 8601.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationError("Timestamp must be timezone-aware.")


def validate_artifact(
    artifact: Artifact, *, expected_workspace_id: str | None = None, require_hash: bool = True
) -> Artifact:
    validate_artifact_id(artifact.id)
    validate_workspace_id(artifact.workspace_id)
    if expected_workspace_id is not None and artifact.workspace_id != expected_workspace_id:
        raise ValidationError("Artifact workspace ID does not match the active workspace.")
    if artifact.type not in ARTIFACT_TYPES or artifact.schema_version != SCHEMA_VERSION:
        raise ValidationError("Artifact type or schema version is unsupported.")
    if not isinstance(artifact.title, str) or not artifact.title.strip():
        raise ValidationError("Artifact title must contain non-whitespace text.")
    if artifact.status not in _STATUSES:
        raise ValidationError("Artifact status is invalid.")
    if artifact.sensitivity not in _SENSITIVITIES:
        raise ValidationError("Artifact sensitivity is invalid.")
    _validate_timestamp(artifact.created_at)
    _validate_timestamp(artifact.updated_at)
    if not artifact.authors:
        raise ValidationError("Artifact authors must be non-empty.")
    for author in artifact.authors:
        if author.kind not in {"human", "system"} or not author.id:
            raise ValidationError("Artifact authors are invalid.")
    from peos.domain.relations.model import materialize_links

    materialize_links(artifact.id, artifact.links, artifact.content_hash)
    if artifact.type == "knowledge.concept" and artifact.payload is not None:
        raise ValidationError("Knowledge concepts do not accept a payload.")
    if artifact.type.startswith("research."):
        from peos.domain.research.artifacts import validate_research_payload

        validate_research_payload(artifact.type, artifact.payload)
    if artifact.type.startswith("project."):
        from peos.domain.project.artifacts import validate_project_payload

        validate_project_payload(artifact.type, artifact.payload, artifact.body)
    if artifact.type.startswith("learning."):
        from peos.domain.learning.artifacts import validate_learning_payload

        validate_learning_payload(artifact.type, artifact.payload)
    provenance = artifact.provenance
    if provenance.producer == "human":
        if (
            provenance.run_id is not None
            or provenance.source_refs
            or artifact.authors != (Author("human", "user"),)
        ):
            raise ValidationError("Human provenance must have human/user authors and no sources.")
    elif provenance.producer == "system":
        if not isinstance(provenance.run_id, str) or not re.fullmatch(
            r"run_[0-9a-f]{32}", provenance.run_id
        ):
            raise ValidationError("System provenance run ID is invalid.")
        if not any(author.kind == "system" for author in artifact.authors) or (
            not provenance.source_refs
            and artifact.type != "research.question"
            and not artifact.type.startswith("project.")
            and artifact.type != "learning.goal"
        ):
            raise ValidationError("System provenance requires a system author and sources.")
        for source in provenance.source_refs:
            if not isinstance(source, dict) or set(source) != {"artifact_id", "content_hash"}:
                raise ValidationError("System source references are invalid.")
            validate_artifact_id(source["artifact_id"])
            if not isinstance(source["content_hash"], str) or not CONTENT_HASH_PATTERN.fullmatch(
                source["content_hash"]
            ):
                raise ValidationError("System source content hash is invalid.")
    else:
        raise ValidationError("Artifact provenance producer is invalid.")
    normalized_body = normalize_body(artifact.body)
    normalized_tags = normalize_tags(list(artifact.tags))
    if require_hash:
        if artifact.content_hash is None or not CONTENT_HASH_PATTERN.fullmatch(
            artifact.content_hash
        ):
            raise ValidationError("Artifact content hash has an invalid format.")
    elif artifact.content_hash is not None:
        raise ValidationError("Pre-save artifact must not contain a content hash.")
    return Artifact(
        **{
            **artifact.__dict__,
            "title": artifact.title.strip(),
            "body": normalized_body,
            "tags": normalized_tags,
        }
    )


def artifact_from_mapping(data: object, body: str) -> Artifact:
    fields = set(data) if isinstance(data, dict) else set()
    if not isinstance(data, dict) or fields not in (
        set(_ENVELOPE_FIELDS),
        set(_ENVELOPE_FIELDS) | {"payload"},
    ):
        raise ValidationError("Artifact envelope fields are invalid.")
    authors = data["authors"]
    provenance = data["provenance"]
    integrity = data["integrity"]
    if not isinstance(authors, list) or not all(
        isinstance(item, dict) and set(item) == {"kind", "id"} for item in authors
    ):
        raise ValidationError("Artifact authors fields are invalid.")
    if not isinstance(provenance, dict) or set(provenance) != {"producer", "run_id", "source_refs"}:
        raise ValidationError("Artifact provenance fields are invalid.")
    if not isinstance(integrity, dict) or set(integrity) != {"content_hash"}:
        raise ValidationError("Artifact integrity fields are invalid.")
    if not isinstance(data["tags"], list) or not isinstance(data["links"], list):
        raise ValidationError("Artifact tags or links are invalid.")
    if not isinstance(provenance["source_refs"], list):
        raise ValidationError("Artifact provenance source references are invalid.")
    artifact = Artifact(
        id=data["id"],
        type=data["type"],
        schema_version=data["schema_version"],
        title=data["title"],
        status=data["status"],
        workspace_id=data["workspace_id"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        authors=tuple(Author(**item) for item in authors),
        sensitivity=data["sensitivity"],
        tags=tuple(data["tags"]),
        links=tuple(data["links"]),
        provenance=Provenance(
            producer=provenance["producer"],
            run_id=provenance["run_id"],
            source_refs=tuple(provenance["source_refs"]),
        ),
        content_hash=integrity["content_hash"],
        body=body,
        payload=data.get("payload"),
    )
    return validate_artifact(artifact)


def envelope_without_integrity(artifact: Artifact) -> dict[str, object]:
    result: dict[str, object] = {
        "id": artifact.id,
        "type": artifact.type,
        "schema_version": artifact.schema_version,
        "title": artifact.title,
        "status": artifact.status,
        "workspace_id": artifact.workspace_id,
        "created_at": artifact.created_at,
        "updated_at": artifact.updated_at,
        "authors": [{"kind": author.kind, "id": author.id} for author in artifact.authors],
        "sensitivity": artifact.sensitivity,
        "tags": list(artifact.tags),
        "links": list(artifact.links),
        "provenance": {
            "producer": artifact.provenance.producer,
            "run_id": artifact.provenance.run_id,
            "source_refs": list(artifact.provenance.source_refs),
        },
    }
    if artifact.payload is not None:
        result["payload"] = artifact.payload
    return result
