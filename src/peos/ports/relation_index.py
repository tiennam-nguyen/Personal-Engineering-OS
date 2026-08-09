"""Read-only derived relation projection contract."""

from __future__ import annotations

from typing import Protocol

from peos.domain.relations.model import RelationEdge


class RelationIndex(Protocol):
    def outgoing(self, artifact_id: str) -> list[RelationEdge]: ...

    def incoming(self, artifact_id: str) -> list[RelationEdge]: ...
