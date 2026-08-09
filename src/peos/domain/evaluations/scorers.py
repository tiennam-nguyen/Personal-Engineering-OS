"""Fixed M8 scorer registry; fixture data cannot select executable code."""

from __future__ import annotations

from peos.domain.evaluations.model import BudgetLimits, ResourceUsage, ScorerOutcome
from peos.domain.models.response import validate_candidate_claim_set, validate_summary_output
from peos.domain.runs.model import canonical_json


def contract_score(task_kind: str, actual: object, fixture: dict[str, object]) -> ScorerOutcome:
    try:
        if task_kind == "summarization":
            validate_summary_output(
                actual, str(fixture["source_artifact_id"]), str(fixture["source_revision"])
            )
        elif task_kind == "claim_extraction":
            blocks = fixture["untrusted_source_blocks"]
            if not isinstance(blocks, list):
                raise ValueError("source blocks")
            validate_candidate_claim_set(
                actual, str(fixture["question_artifact_id"]), tuple(blocks)
            )
        elif task_kind == "project_planning":
            _validate_project(actual, fixture)
        else:
            raise ValueError("task kind")
    except Exception:
        return ScorerOutcome("deterministic.contract.v1", False, ("output_contract_invalid",))
    return ScorerOutcome("deterministic.contract.v1", True, ())


def budget_score(usage: ResourceUsage, budget: BudgetLimits) -> ScorerOutcome:
    checks = {
        "provider_calls_exceeded": usage.provider_calls <= budget.max_provider_calls_per_case,
        "input_tokens_exceeded": usage.input_tokens <= budget.max_input_tokens_per_case,
        "output_tokens_exceeded": usage.output_tokens <= budget.max_output_tokens_per_case,
        "input_bytes_exceeded": usage.input_bytes <= budget.max_input_bytes_per_case,
        "output_bytes_exceeded": usage.output_bytes <= budget.max_output_bytes_per_case,
        "cache_used": usage.cache_hit_count == 0,
    }
    reasons = tuple(code for code, passed in checks.items() if not passed)
    return ScorerOutcome("deterministic.budget.v1", not reasons, reasons)


def exact_output_score(actual: object, expected: object) -> ScorerOutcome:
    passed = canonical_json(actual) == canonical_json(expected)
    return ScorerOutcome(
        "reference.exact_output.v1",
        passed,
        () if passed else ("exact_output_mismatch",),
    )


def _validate_project(value: object, fixture: dict[str, object]) -> None:
    keys = {"schema_version", "objective", "requirements", "architecture", "walking_skeleton"}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("project keys")
    objective, architecture, skeleton = (
        value["objective"],
        value["architecture"],
        value["walking_skeleton"],
    )
    if (
        not isinstance(objective, dict)
        or not isinstance(architecture, dict)
        or not isinstance(skeleton, dict)
    ):
        raise ValueError("project objects")
    if not 1 <= len(objective.get("optimized_attributes", [])) <= 3:
        raise ValueError("optimized attributes")
    if fixture["intolerable_failure"] not in objective.get("non_negotiables", []):
        raise ValueError("intolerable failure")
    if not {"main_design", "pre_mortem", "orthogonal", "shadow_review"} <= set(architecture):
        raise ValueError("3+1")
    allowed, candidates = skeleton.get("allowed_paths"), fixture["candidate_change_paths"]
    if not isinstance(allowed, list) or not isinstance(candidates, list):
        raise ValueError("scope lists")
    if not set(allowed) <= set(candidates):
        raise ValueError("scope")
