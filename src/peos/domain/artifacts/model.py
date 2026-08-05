"""Storage-neutral immutable artifact values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Author:
    kind: str
    id: str


@dataclass(frozen=True)
class Provenance:
    producer: str
    run_id: str | None
    source_refs: tuple[object, ...]


@dataclass(frozen=True)
class Artifact:
    id: str
    type: str
    schema_version: int
    title: str
    status: str
    workspace_id: str
    created_at: str
    updated_at: str
    authors: tuple[Author, ...]
    sensitivity: str
    tags: tuple[str, ...]
    links: tuple[object, ...]
    provenance: Provenance
    content_hash: str | None
    body: str
    payload: dict[str, object] | None = None


@dataclass(frozen=True)
class StoredArtifact:
    artifact: Artifact
    canonical_path: str


@dataclass(frozen=True)
class SearchResult:
    id: str
    type: str
    title: str
    status: str
    sensitivity: str
    canonical_path: str
    content_hash: str
