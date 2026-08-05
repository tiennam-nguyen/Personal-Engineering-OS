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
    max_untrusted_source_bytes: int = 1048576
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
    untrusted_source_blocks: tuple[object, ...]
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
        source_hashes: list[str] = []
        for item in self.untrusted_source_blocks:
            if self.task_kind == "claim_extraction" and isinstance(item, dict):
                stable = {
                    key: value
                    for key, value in item.items()
                    if key not in {"source_artifact_id", "source_revision"}
                }
                source_hashes.append(sha256(stable))
            else:
                source_hashes.append(sha256(item))
        return sha256(
            {
                "task_kind": self.task_kind,
                "protocol": asdict(self.protocol_ref),
                "host_system_instructions": sha256(self.host_system_instructions),
                "step_instructions": sha256(self.step_instructions),
                "trusted_user_intent": sha256(self.trusted_user_intent),
                "context_manifest_hash": self.context_manifest_hash,
                "untrusted_source_hashes": source_hashes,
                "output_schema_hash": sha256(self.output_schema),
                "capability_requirements": sorted(self.capability_requirements),
                "sensitivity": self.sensitivity,
                "parameters": self.parameters,
                "workflow_step_version": self.workflow_step_version,
            }
        )
