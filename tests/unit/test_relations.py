from __future__ import annotations

from dataclasses import replace

import pytest

from peos.adapters.filesystem.codec import calculate_hash, serialize, verify
from peos.domain.artifacts.model import Artifact, Author, Provenance
from peos.domain.errors import ValidationError
from peos.domain.relations.model import materialize_links

A = "art_" + "a" * 32
B = "art_" + "b" * 32


def _artifact(links: tuple[object, ...]) -> Artifact:
    base = Artifact(
        A,
        "knowledge.concept",
        1,
        "A",
        "draft",
        "ws_" + "1" * 32,
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00Z",
        (Author("human", "user"),),
        "private",
        (),
        links,
        Provenance("human", None, ()),
        None,
        "Body\n",
    )
    return replace(base, content_hash=calculate_hash(base))


def test_link_variants_are_strict_and_legacy_bytes_round_trip() -> None:
    outgoing = _artifact(({"rel": "references", "target": B},))
    raw = serialize(outgoing)
    assert serialize(verify(raw).artifact) == raw
    assert materialize_links(A, outgoing.links)[0].logical_key == (A, "references", B)
    incoming = _artifact(({"source": B, "rel": "supports"},))
    assert materialize_links(A, incoming.links)[0].logical_key == (B, "supports", A)
    assert b"source: art_" in serialize(incoming)
    invalid: tuple[dict[str, object], ...] = (
        {},
        {"source": B, "target": B, "rel": "supports"},
        {"source": B, "rel": "supports", "extra": True},
        {"source": "bad", "rel": "supports"},
        {"rel": "unknown", "target": B},
    )
    for link in invalid:
        with pytest.raises(ValidationError):
            materialize_links(A, (link,))
    with pytest.raises(ValidationError):
        materialize_links(
            A, ({"rel": "references", "target": B}, {"rel": "references", "target": B})
        )
