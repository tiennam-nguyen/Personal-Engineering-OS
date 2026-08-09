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
        if request.task_kind == "project_planning":
            return self._plan_project(request)
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

    def _plan_project(self, request: ModelRequest) -> ModelResponse:
        if request.capability_requirements != frozenset({"structured_output"}):
            raise ModelCapabilityMismatch("Deterministic project planning request is incompatible.")
        try:
            intent = __import__("json").loads(request.trusted_user_intent)
        except (TypeError, ValueError) as error:
            raise ModelGatewayError("Trusted project intent is malformed.") from error
        if not isinstance(intent, dict):
            raise ModelGatewayError("Trusted project intent is malformed.")
        reads = intent["reads"]
        candidates = list(intent["candidate_change_paths"])
        forbidden = list(intent["forbidden_change_paths"])
        output = {
            "schema_version": 1,
            "objective": {
                "mission": intent["request"],
                "stakeholder": intent["stakeholder"],
                "optimized_attributes": ["scope safety", "repository provenance", "recoverability"],
                "deliberate_sacrifices": ["general repository comprehension", "automatic coding"],
                "non_negotiables": [intent["intolerable_failure"], *intent["constraints"]],
                "assumptions": [],
                "scope_exclusions": ["autonomous repository modification", "command execution"],
            },
            "requirements": [
                {
                    "key": "REQ-001",
                    "actor": intent["stakeholder"],
                    "trigger": "the walking skeleton is implemented",
                    "observable_behavior": intent["definition_of_done"],
                    "constraints": intent["constraints"],
                    "failure_behavior": intent["intolerable_failure"],
                    "priority": "must",
                    "acceptance": {
                        "method": "reported_command",
                        "expected_evidence": intent["expected_evidence"],
                    },
                    "source": "project_request",
                }
            ],
            "architecture": {
                "main_design": "Make the minimum change inside the approved paths.",
                "pre_mortem": "Scope escape or regression invalidates the result.",
                "orthogonal": "Check whether tests or documentation alone can meet the objective.",
                "shadow_review": "Review maintainability, scope, and recovery before acceptance.",
                "door_decisions": [
                    {
                        "decision": "Preserve the public contract",
                        "classification": "one_way",
                        "treatment_kind": "seam",
                        "treatment": "Keep the change behind existing boundaries.",
                    }
                ],
                "trade_ledger": [
                    {
                        "gained": "bounded change",
                        "lost": "broad redesign",
                        "who_pays": "implementer",
                        "when_due": "this milestone",
                        "compounds": "no",
                    }
                ],
                "recommendation": "Implement and verify the single walking skeleton.",
                "falsifier": "A required change lies outside the approved paths.",
                "repository_claims": [
                    {
                        "claim": "These files were explicitly read by PEOS.",
                        "evidence_paths": [item["path"] for item in reads],
                    }
                ],
            },
            "walking_skeleton": {
                "key": "M1",
                "objective": intent["request"],
                "allowed_paths": candidates,
                "forbidden_paths": forbidden,
                "deliverables": [intent["definition_of_done"]],
                "definition_of_done": intent["definition_of_done"],
                "rollback_recovery": (
                    "Revert only approved changed files using the target repository recovery path."
                ),
                "risks": [intent["intolerable_failure"]],
                "assumptions": [],
            },
        }
        content = canonical_json(output).decode("utf-8")
        fingerprint = request.fingerprint()
        self.invocation_count += 1
        return ModelResponse(
            "mock",
            "deterministic-project-planner-v1",
            "1",
            "mockreq_" + fingerprint.removeprefix("sha256:")[:32],
            content,
            output,
            UsageRecord(
                0, len(re.findall(r"\S+", content)), "mock_whitespace_v1", 0, len(content.encode())
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
