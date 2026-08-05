"""Canonical Markdown/YAML encoding and independent integrity verification."""

from __future__ import annotations

import hashlib
import hmac
from typing import cast

import yaml  # type: ignore[import-untyped]

from peos.domain.artifacts.model import Artifact, StoredArtifact
from peos.domain.artifacts.validation import (
    artifact_from_mapping,
    envelope_without_integrity,
    validate_artifact,
)
from peos.domain.errors import IntegrityVerificationError, ValidationError


def _dump(mapping: dict[str, object]) -> bytes:
    text = yaml.safe_dump(
        mapping, sort_keys=False, allow_unicode=True, default_flow_style=False, width=4096
    )
    return cast(bytes, text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))


def _hash_input(artifact: Artifact) -> bytes:
    front_matter = _dump(envelope_without_integrity(artifact))
    return b"---\n" + front_matter + b"---\n\n" + artifact.body.encode("utf-8")


def calculate_hash(artifact: Artifact) -> str:
    validated = validate_artifact(artifact, require_hash=False)
    return "sha256:" + hashlib.sha256(_hash_input(validated)).hexdigest()


def serialize(artifact: Artifact) -> bytes:
    validated = validate_artifact(artifact, require_hash=True)
    envelope = envelope_without_integrity(validated)
    envelope["integrity"] = {"content_hash": validated.content_hash}
    return b"---\n" + _dump(envelope) + b"---\n\n" + validated.body.encode("utf-8")


def parse(data: bytes, canonical_path: str = "") -> StoredArtifact:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError("Canonical artifact is not UTF-8.") from error
    if not text.startswith("---\n"):
        raise ValidationError("Canonical artifact front matter opening delimiter is missing.")
    end = text.find("\n---\n\n", 4)
    if end == -1:
        raise ValidationError("Canonical artifact front matter closing delimiter is missing.")
    yaml_text = text[4:end]
    body = text[end + len("\n---\n\n") :]
    try:
        envelope = yaml.safe_load(yaml_text)
    except yaml.YAMLError as error:
        raise ValidationError("Canonical artifact YAML is malformed.") from error
    artifact = artifact_from_mapping(envelope, body)
    return StoredArtifact(artifact=artifact, canonical_path=canonical_path)


def verify(data: bytes, canonical_path: str = "") -> StoredArtifact:
    stored = parse(data, canonical_path)
    recomputed = calculate_hash(Artifact(**{**stored.artifact.__dict__, "content_hash": None}))
    expected = stored.artifact.content_hash
    if expected is None or not hmac.compare_digest(expected, recomputed):
        raise IntegrityVerificationError("Canonical artifact content hash does not match.")
    return stored
