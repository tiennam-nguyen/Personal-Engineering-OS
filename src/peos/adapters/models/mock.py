"""No-network deterministic summarization gateway."""

from __future__ import annotations

import re

from peos.domain.errors import ModelCapabilityMismatch, ModelGatewayError
from peos.domain.models.request import ModelRequest
from peos.domain.models.response import ModelResponse, UsageRecord, validate_summary_output
from peos.domain.runs.model import canonical_json


class DeterministicMockGateway:
    provider = "mock"
    model = "deterministic-concept-summary-v1"
    model_revision = "1"
    capabilities = frozenset({"structured_output"})
    sensitivity_ceiling = "private"
    invocation_count = 0

    def generate(self, request: ModelRequest) -> ModelResponse:
        if (
            request.task_kind != "summarization"
            or request.capability_requirements != self.capabilities
            or len(request.context_blocks) != 1
        ):
            raise ModelCapabilityMismatch("Deterministic mock request is incompatible.")
        if request.sensitivity not in {"public", "private"}:
            raise ModelGatewayError("Mock route sensitivity is unsupported.")
        block = request.context_blocks[0]
        if not block.content.startswith("Title: ") or "\n\n" not in block.content:
            raise ModelGatewayError("Mock context block is malformed.")
        title, body = block.content[7:].split("\n\n", 1)
        summary = re.sub(r"\s+", " ", body).strip()
        summary = summary if len(summary) <= 320 else summary[:317] + "..."
        output = validate_summary_output(
            {
                "schema_version": 1,
                "title": f"Model summary: {title}",
                "summary": summary,
                "source_artifact_id": block.artifact_id,
                "source_revision": block.revision,
            },
            block.artifact_id,
            block.revision,
        )
        content = canonical_json(output).decode("utf-8")
        input_text = "\n".join(
            (
                request.host_system_instructions,
                request.protocol_instructions,
                request.step_instructions,
                request.trusted_user_intent,
                block.content,
                canonical_json(request.output_schema).decode("utf-8"),
            )
        )

        def tokens(text: str) -> int:
            return len(re.findall(r"\S+", text))

        fingerprint = request.fingerprint()
        self.invocation_count += 1
        return ModelResponse(
            self.provider,
            self.model,
            self.model_revision,
            "mockreq_" + fingerprint.removeprefix("sha256:")[:32],
            content,
            output,
            UsageRecord(
                tokens(input_text),
                tokens(content),
                "mock_whitespace_v1",
                len(input_text.encode()),
                len(content.encode()),
            ),
            "stop",
            None,
        )
