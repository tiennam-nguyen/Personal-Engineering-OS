"""Immutable research locator and claim values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLocator:
    source_artifact_id: str
    source_artifact_revision: str
    object_hash: str
    line_start: int
    line_end: int
    byte_start: int
    byte_end: int
    excerpt_hash: str


@dataclass(frozen=True)
class CandidateClaim:
    proposition: str
    polarity: str
    locator: SourceLocator


@dataclass(frozen=True)
class NormalizedClaim:
    proposition: str
    semantic_key: str
    polarity: str
    evidence_status: str
    evidence_refs: tuple[SourceLocator, ...]
