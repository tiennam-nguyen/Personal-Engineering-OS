from dataclasses import replace

import pytest

from peos.domain.context.model import ContextBlock
from peos.domain.errors import ValidationError
from peos.domain.models.audit import ModelRoute, cache_key
from peos.domain.models.request import ModelBudget, ModelRequest, ProtocolRef
from peos.domain.models.response import output_schema, validate_summary_output


def request() -> ModelRequest:
    block = ContextBlock(
        "art_" + "a" * 32,
        "sha256:" + "b" * 64,
        "knowledge.concept",
        "workspace_verified",
        "private",
        "explicit",
        "artifacts/knowledge/x.md",
        8,
        "Title: T\n\nBody",
    )
    return ModelRequest(
        "summarization",
        ProtocolRef("sample.concept-summary", "1.0.0", "sha256:" + "c" * 64),
        "host",
        "protocol",
        "step",
        "intent",
        (block,),
        (block.content,),
        output_schema(),
        frozenset({"structured_output"}),
        "private",
        ModelBudget(),
        "use",
        {"temperature": 0},
        {"run_id": "run_a"},
        "sha256:" + "d" * 64,
        "1.0.0",
    )


def test_request_fingerprint_excludes_execution_identity() -> None:
    original = request()
    assert (
        original.fingerprint()
        == replace(original, metadata={"run_id": "run_b", "call_id": "call_b"}).fingerprint()
    )


def test_load_bearing_request_fields_change_fingerprint() -> None:
    original = request()
    variants = (
        replace(original, task_kind="other"),
        replace(original, step_instructions="changed"),
        replace(original, trusted_user_intent="changed"),
        replace(original, sensitivity="public"),
        replace(original, workflow_step_version="2.0.0"),
    )
    assert all(original.fingerprint() != item.fingerprint() for item in variants)


def test_cache_key_excludes_execution_identity_and_policy() -> None:
    original = request()
    assert cache_key(original, ModelRoute()) == cache_key(
        replace(original, metadata={"run_id": "other"}, cache_policy="bypass"), ModelRoute()
    )


def test_strict_output_rejects_unknown_key_and_source_mismatch() -> None:
    source_id, revision = "art_" + "a" * 32, "sha256:" + "b" * 64
    valid = {
        "schema_version": 1,
        "title": "T",
        "summary": "S",
        "source_artifact_id": source_id,
        "source_revision": revision,
    }
    with pytest.raises(ValidationError):
        validate_summary_output(valid | {"extra": True}, source_id, revision)
    with pytest.raises(ValidationError):
        validate_summary_output(valid, "art_" + "c" * 32, revision)
