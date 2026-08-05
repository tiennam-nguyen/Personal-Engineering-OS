"""Deterministic cache and budget values for model calls."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from peos.domain.errors import BudgetExceeded, ValidationError
from peos.domain.models.request import ModelBudget, ModelRequest
from peos.domain.models.response import ModelResponse
from peos.domain.runs.model import sha256


@dataclass(frozen=True)
class ModelRoute:
    provider: str = "mock"
    model: str = "deterministic-concept-summary-v1"
    model_revision: str = "1"
    capabilities: frozenset[str] = frozenset({"structured_output"})
    sensitivity_ceiling: str = "private"


@dataclass(frozen=True)
class CachePolicy:
    mode: str = "use"

    def __post_init__(self) -> None:
        if self.mode not in {"use", "bypass"}:
            raise ValidationError("Cache policy must be use or bypass.")


def cache_key(request: ModelRequest, route: ModelRoute) -> str:
    return sha256(
        {
            "provider": route.provider,
            "model": route.model,
            "model_revision": route.model_revision,
            "protocol_hash": request.protocol_ref.sha256,
            "workflow_step_version": request.workflow_step_version,
            "parameters": request.parameters,
            "request_fingerprint": request.fingerprint(),
            "context_manifest_fingerprint": request.context_manifest_hash,
            "output_schema_hash": sha256(request.output_schema),
            "tool_result_hashes": [],
        }
    )


def response_hash(response: ModelResponse) -> str:
    return sha256(
        {
            "provider": response.provider,
            "model": response.model,
            "model_revision": response.model_revision,
            "provider_request_id": response.provider_request_id,
            "content": response.content,
            "parsed_output": response.parsed_output,
            "usage": asdict(response.usage),
            "finish_reason": response.finish_reason,
            "raw_response_ref": response.raw_response_ref,
        }
    )


def enforce_budget(
    budget: ModelBudget,
    *,
    provider_calls: int,
    context_bytes: int,
    untrusted_source_bytes: int = 0,
    response: ModelResponse | None = None,
    wall_seconds: float = 0.0,
) -> dict[str, object]:
    usage = None if response is None else response.usage
    checks = {
        "provider calls": provider_calls <= budget.max_calls,
        "context bytes": context_bytes <= budget.max_context_bytes,
        "untrusted source bytes": untrusted_source_bytes <= budget.max_untrusted_source_bytes,
        "input tokens": usage is None or usage.input_tokens <= budget.max_input_tokens,
        "output tokens": usage is None or usage.output_tokens <= budget.max_output_tokens,
        "output bytes": usage is None or usage.output_bytes <= budget.max_output_bytes,
        "wall seconds": wall_seconds <= budget.max_wall_seconds,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise BudgetExceeded("Model budget exceeded: " + ", ".join(failed) + ".")
    return {
        "limits": asdict(budget),
        "provider_calls": provider_calls,
        "cache_hit_count": 1 if provider_calls == 0 and response is not None else 0,
        "context_bytes": context_bytes,
        "untrusted_source_bytes": untrusted_source_bytes,
        "input_tokens": 0 if usage is None else usage.input_tokens,
        "output_tokens": 0 if usage is None else usage.output_tokens,
        "input_bytes": 0 if usage is None else usage.input_bytes,
        "output_bytes": 0 if usage is None else usage.output_bytes,
        "wall_seconds": wall_seconds,
        "token_measurement": None if usage is None else usage.token_measurement,
        "monetary_cost": None,
        "pricing_status": "unknown",
        "passed": True,
    }
