"""No-network deterministic summarization gateway."""

from __future__ import annotations

import re

from peos.domain.errors import ModelCapabilityMismatch, ModelGatewayError
from peos.domain.models.request import ModelRequest
from peos.domain.models.response import (
    ModelResponse,
    UsageRecord,
    validate_candidate_claim_set,
    validate_summary_output,
)
from peos.domain.runs.model import canonical_json


class DeterministicMockGateway:
    provider = "mock"
    model = "deterministic-concept-summary-v1"
    model_revision = "1"
    capabilities = frozenset({"structured_output"})
    sensitivity_ceiling = "private"
    invocation_count = 0

    def generate(self, request: ModelRequest) -> ModelResponse:
        if request.task_kind == "claim_extraction":
            return self._extract_claims(request)
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

    def _extract_claims(self, request: ModelRequest) -> ModelResponse:
        if (
            request.capability_requirements != frozenset({"structured_output", "source_locators"})
            or len(request.context_blocks) != 1
        ):
            raise ModelCapabilityMismatch("Deterministic claim extraction request is incompatible.")
        claims: list[dict[str, object]] = []
        for item in request.untrusted_source_blocks:
            if not isinstance(item, dict) or item.get("trust") != "untrusted_external_content":
                raise ModelCapabilityMismatch("Untrusted source block is invalid.")
            content = item.get("content")
            if not isinstance(content, str):
                raise ModelCapabilityMismatch("Untrusted source content is invalid.")
            proposition = re.sub(r"\s+", " ", content).strip()
            if not proposition or proposition.startswith("#") or proposition.endswith("?"):
                continue
            tokens = re.findall(r"\S+", proposition)
            polarity = (
                "negative" if any(token.casefold() == "not" for token in tokens) else "positive"
            )
            locator_keys = (
                "source_artifact_id",
                "source_revision",
                "object_hash",
                "line_start",
                "line_end",
                "byte_start",
                "byte_end",
                "excerpt_hash",
            )
            claims.append(
                {
                    "proposition": proposition,
                    "polarity": polarity,
                    **{key: item[key] for key in locator_keys},
                }
            )
        question_id = request.context_blocks[0].artifact_id
        output = validate_candidate_claim_set(
            {"schema_version": 1, "question_artifact_id": question_id, "claims": claims},
            question_id,
            request.untrusted_source_blocks,
        )
        content = canonical_json(output).decode("utf-8")
        input_text = canonical_json(
            {
                "context": [block.content for block in request.context_blocks],
                "sources": list(request.untrusted_source_blocks),
                "schema": request.output_schema,
            }
        ).decode("utf-8")
        fingerprint = request.fingerprint()
        self.invocation_count += 1
        return ModelResponse(
            "mock",
            "deterministic-claim-extractor-v1",
            "1",
            "mockreq_" + fingerprint.removeprefix("sha256:")[:32],
            content,
            output,
            UsageRecord(
                len(re.findall(r"\S+", input_text)),
                len(re.findall(r"\S+", content)),
                "mock_whitespace_v1",
                len(input_text.encode()),
                len(content.encode()),
            ),
            "stop",
            None,
        )
