"""Validated mock response values and the one supported output contract."""

from __future__ import annotations

from dataclasses import dataclass

from peos.domain.artifacts.validation import CONTENT_HASH_PATTERN, validate_artifact_id
from peos.domain.errors import ValidationError


@dataclass(frozen=True)
class UsageRecord:
    input_tokens: int
    output_tokens: int
    token_measurement: str
    input_bytes: int
    output_bytes: int


@dataclass(frozen=True)
class ModelResponse:
    provider: str
    model: str
    model_revision: str
    provider_request_id: str
    content: str
    parsed_output: dict[str, object]
    usage: UsageRecord
    finish_reason: str
    raw_response_ref: str | None


def output_schema() -> dict[str, object]:
    return {
        "schema_version": 1,
        "title": "string<=200",
        "summary": "string<=4000",
        "source_artifact_id": "art_...",
        "source_revision": "sha256:...",
    }


def validate_summary_output(
    value: object, source_id: str, source_revision: str
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "title",
        "summary",
        "source_artifact_id",
        "source_revision",
    }:
        raise ValidationError("Model output contract is invalid.")
    title, summary = value["title"], value["summary"]
    if (
        value["schema_version"] != 1
        or not isinstance(title, str)
        or not title.strip()
        or len(title.strip()) > 200
        or not isinstance(summary, str)
        or not summary.strip()
        or len(summary.strip()) > 4000
    ):
        raise ValidationError("Model summary fields are invalid.")
    validate_artifact_id(str(value["source_artifact_id"]))
    if not isinstance(value["source_revision"], str) or not CONTENT_HASH_PATTERN.fullmatch(
        value["source_revision"]
    ):
        raise ValidationError("Model source revision is invalid.")
    if value["source_artifact_id"] != source_id or value["source_revision"] != source_revision:
        raise ValidationError("Model output source does not match verified context.")
    return {**value, "title": title.strip(), "summary": summary.strip()}
