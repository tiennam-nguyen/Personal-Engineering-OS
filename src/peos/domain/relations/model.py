"""Strict hosted-link parsing and deterministic edge materialization."""

from __future__ import annotations

from dataclasses import dataclass

from peos.domain.artifacts.validation import validate_artifact_id
from peos.domain.errors import ValidationError

RELATION_TYPES = frozenset(
    {"derived_from", "supports", "contradicts", "references", "produced_by", "supersedes"}
)


@dataclass(frozen=True, order=True)
class RelationEdge:
    source_artifact_id: str
    relation: str
    target_artifact_id: str
    host_artifact_id: str
    host_revision: str | None = None

    @property
    def logical_key(self) -> tuple[str, str, str]:
        return self.source_artifact_id, self.relation, self.target_artifact_id


def materialize_links(
    host_artifact_id: str, links: tuple[object, ...], host_revision: str | None = None
) -> tuple[RelationEdge, ...]:
    validate_artifact_id(host_artifact_id)
    edges: list[RelationEdge] = []
    seen: set[tuple[str, str, str]] = set()
    for link in links:
        if not isinstance(link, dict):
            raise ValidationError("Artifact link must be an object.")
        fields = set(link)
        if fields == {"rel", "target"}:
            source, target = host_artifact_id, link["target"]
        elif fields == {"source", "rel"}:
            source, target = link["source"], host_artifact_id
        else:
            raise ValidationError("Artifact link fields are invalid.")
        relation = link["rel"]
        if (
            relation not in RELATION_TYPES
            or not isinstance(source, str)
            or not isinstance(target, str)
        ):
            raise ValidationError("Artifact relation is invalid.")
        validate_artifact_id(source)
        validate_artifact_id(target)
        edge = RelationEdge(source, relation, target, host_artifact_id, host_revision)
        if edge.logical_key in seen:
            raise ValidationError("Duplicate logical artifact edge is invalid.")
        seen.add(edge.logical_key)
        edges.append(edge)
    return tuple(sorted(edges))
