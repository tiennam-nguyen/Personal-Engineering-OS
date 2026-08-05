"""Structured model request; context remains a data channel."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from peos.domain.context.model import ContextBlock
from peos.domain.runs.model import sha256


@dataclass(frozen=True)
class ProtocolRef:
    name: str
    version: str
    sha256: str


@dataclass(frozen=True)
class ModelBudget:
    max_calls: int = 1
    max_context_bytes: int = 32768
    max_input_tokens: int = 8192
    max_output_tokens: int = 1024
    max_output_bytes: int = 8192
    max_wall_seconds: float = 5.0


@dataclass(frozen=True)
class ModelRequest:
    task_kind: str
    protocol_ref: ProtocolRef
    host_system_instructions: str
    protocol_instructions: str
    step_instructions: str
    trusted_user_intent: str
    context_blocks: tuple[ContextBlock, ...]
    untrusted_source_blocks: tuple[str, ...]
    output_schema: dict[str, object]
    capability_requirements: frozenset[str]
    sensitivity: str
    budget: ModelBudget
    cache_policy: str
    parameters: dict[str, object]
    metadata: dict[str, str]
    context_manifest_hash: str
    workflow_step_version: str

    def fingerprint(self) -> str:
        return sha256(
            {
                "task_kind": self.task_kind,
                "protocol": asdict(self.protocol_ref),
                "host_system_instructions": sha256(self.host_system_instructions),
                "step_instructions": sha256(self.step_instructions),
                "trusted_user_intent": sha256(self.trusted_user_intent),
                "context_manifest_hash": self.context_manifest_hash,
                "untrusted_source_hashes": [sha256(item) for item in self.untrusted_source_blocks],
                "output_schema_hash": sha256(self.output_schema),
                "capability_requirements": sorted(self.capability_requirements),
                "sensitivity": self.sensitivity,
                "parameters": self.parameters,
                "workflow_step_version": self.workflow_step_version,
            }
        )
