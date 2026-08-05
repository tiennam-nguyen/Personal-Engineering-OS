from dataclasses import replace

import pytest

from peos.adapters.models.mock import DeterministicMockGateway
from peos.domain.context.model import ContextBlock
from peos.domain.errors import ModelCapabilityMismatch
from peos.domain.models.request import ModelBudget, ModelRequest, ProtocolRef
from peos.domain.models.response import output_schema


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
        {},
        "sha256:" + "d" * 64,
        "1.0.0",
    )


def test_mock_is_deterministic_and_preserves_source() -> None:
    gateway = DeterministicMockGateway()
    first, second = gateway.generate(request()), gateway.generate(request())
    assert first == second
    assert (
        first.provider_request_id
        == "mockreq_" + request().fingerprint().removeprefix("sha256:")[:32]
    )
    assert first.parsed_output["source_artifact_id"] == request().context_blocks[0].artifact_id
    assert first.usage.token_measurement == "mock_whitespace_v1"


def test_mock_rejects_unknown_task_and_multiple_context_blocks() -> None:
    gateway = DeterministicMockGateway()
    with pytest.raises(ModelCapabilityMismatch):
        gateway.generate(replace(request(), task_kind="research"))
    with pytest.raises(ModelCapabilityMismatch):
        gateway.generate(replace(request(), context_blocks=request().context_blocks * 2))
