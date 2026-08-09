"""Read-only graph traversal with canonical-host verification."""

from __future__ import annotations

from collections import deque

from peos.domain.artifacts.validation import validate_artifact_id
from peos.domain.errors import GraphProjectionDivergence, PeosError
from peos.domain.relations.model import RelationEdge, materialize_links
from peos.ports.artifact_index import ArtifactIndex
from peos.ports.artifact_repository import ArtifactRepository
from peos.ports.relation_index import RelationIndex


class GraphService:
    def __init__(
        self,
        artifacts: ArtifactRepository,
        artifact_index: ArtifactIndex,
        relations: RelationIndex,
        workspace_command: str,
    ) -> None:
        self._artifacts = artifacts
        self._artifact_index = artifact_index
        self._relations = relations
        self._recovery = f"{workspace_command} index rebuild"

    def traverse(self, root_artifact_id: str, depth: int = 1) -> dict[str, object]:
        validate_artifact_id(root_artifact_id)
        if depth < 0:
            raise GraphProjectionDivergence("Graph depth cannot be negative.")
        root = self._canonical(root_artifact_id)
        nodes = {root_artifact_id: (root, 0)}
        edges: dict[tuple[str, str, str], RelationEdge] = {}
        queue = deque([(root_artifact_id, 0)])
        expanded: set[str] = set()
        while queue:
            current, distance = queue.popleft()
            if current in expanded or distance >= depth:
                continue
            expanded.add(current)
            for edge in self._adjacent(current):
                self._verify_edge(edge)
                edges[edge.logical_key] = edge
                for endpoint in (edge.source_artifact_id, edge.target_artifact_id):
                    candidate_distance = distance + 1
                    if endpoint not in nodes or candidate_distance < nodes[endpoint][1]:
                        nodes[endpoint] = (self._canonical(endpoint), candidate_distance)
                        queue.append((endpoint, candidate_distance))
        return {
            "root_artifact_id": root_artifact_id,
            "depth": depth,
            "nodes": [
                {
                    "artifact_id": identifier,
                    "revision": stored.artifact.content_hash,
                    "type": stored.artifact.type,
                    "title": stored.artifact.title,
                    "distance": distance,
                }
                for identifier, (stored, distance) in sorted(
                    nodes.items(), key=lambda item: (item[1][1], item[0])
                )
            ],
            "edges": [
                {
                    "source_artifact_id": edge.source_artifact_id,
                    "relation": edge.relation,
                    "target_artifact_id": edge.target_artifact_id,
                }
                for edge in sorted(edges.values())
            ],
        }

    def _adjacent(self, artifact_id: str) -> list[RelationEdge]:
        try:
            return sorted(
                self._relations.outgoing(artifact_id) + self._relations.incoming(artifact_id)
            )
        except PeosError as error:
            raise GraphProjectionDivergence(
                "Graph relation projection is unavailable.", self._recovery
            ) from error

    def _canonical(self, artifact_id: str):  # type: ignore[no-untyped-def]
        try:
            projected = self._artifact_index.get(artifact_id)
            canonical = self._artifacts.verify(projected.canonical_path)
        except PeosError as error:
            raise GraphProjectionDivergence(
                "Graph projection or canonical endpoint is unavailable.", self._recovery
            ) from error
        if canonical.artifact.content_hash != projected.artifact.content_hash:
            raise GraphProjectionDivergence(
                "Graph endpoint projection differs from canonical.", self._recovery
            )
        return canonical

    def _verify_edge(self, edge: RelationEdge) -> None:
        host = self._canonical(edge.host_artifact_id)
        if host.artifact.content_hash != edge.host_revision:
            raise GraphProjectionDivergence(
                "Relation host revision differs from canonical.", self._recovery
            )
        canonical = {
            item.logical_key
            for item in materialize_links(
                host.artifact.id, host.artifact.links, host.artifact.content_hash
            )
        }
        if edge.logical_key not in canonical:
            raise GraphProjectionDivergence(
                "Relation row is absent from its canonical host.", self._recovery
            )
        self._canonical(edge.source_artifact_id)
        self._canonical(edge.target_artifact_id)
