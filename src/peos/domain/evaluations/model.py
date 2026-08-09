"""Pure values for frozen evaluations; no storage or candidate execution lives here."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum

from peos.domain.errors import EvaluationConfigurationError
from peos.domain.runs.model import sha256

DETERMINISTIC_SCORERS = frozenset({"deterministic.contract.v1", "deterministic.budget.v1"})
REFERENCE_SCORERS = frozenset({"reference.exact_output.v1"})


@dataclass(frozen=True)
class BudgetLimits:
    max_provider_calls_per_case: int
    max_input_tokens_per_case: int
    max_output_tokens_per_case: int
    max_input_bytes_per_case: int
    max_output_bytes_per_case: int

    def __post_init__(self) -> None:
        if any(value <= 0 for value in asdict(self).values()):
            raise EvaluationConfigurationError("Evaluation budget limits must be positive.")


@dataclass(frozen=True)
class EvalCase:
    id: str
    task_kind: str
    input_fixture: dict[str, object]
    expected: dict[str, object]
    tags: tuple[str, ...]
    raw_hash: str


@dataclass(frozen=True)
class EvalSuite:
    name: str
    version: str
    task_kind: str
    raw_hash: str
    protocol_name: str
    protocol_version: str
    protocol_hash: str
    output_contract: str
    output_schema_hash: str
    required_capabilities: frozenset[str]
    sensitivity_ceiling: str
    deterministic_scorers: tuple[str, ...]
    reference_scorers: tuple[str, ...]
    min_reference_pass_rate: float
    budget: BudgetLimits
    cases: tuple[EvalCase, ...]

    def __post_init__(self) -> None:
        if not self.cases or len({case.id for case in self.cases}) != len(self.cases):
            raise EvaluationConfigurationError("Evaluation case IDs must be non-empty and unique.")
        if any(case.task_kind != self.task_kind for case in self.cases):
            raise EvaluationConfigurationError("Evaluation case task kind differs from its suite.")
        if not 0 <= self.min_reference_pass_rate <= 1:
            raise EvaluationConfigurationError("Reference threshold must be between zero and one.")
        if not self.deterministic_scorers or not self.reference_scorers:
            raise EvaluationConfigurationError(
                "Qualification needs deterministic and reference scorers."
            )
        if not set(self.deterministic_scorers) <= DETERMINISTIC_SCORERS:
            raise EvaluationConfigurationError("Unknown deterministic scorer.")
        if not set(self.reference_scorers) <= REFERENCE_SCORERS:
            raise EvaluationConfigurationError("Unknown reference scorer.")


@dataclass(frozen=True)
class CandidateRoute:
    provider: str
    model: str
    model_revision: str
    task_kind: str
    capabilities: frozenset[str]
    sensitivity_ceiling: str


@dataclass(frozen=True)
class ScorerOutcome:
    scorer: str
    passed: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ResourceUsage:
    provider_calls: int
    cache_hit_count: int
    input_bytes: int
    output_bytes: int
    input_tokens: int
    output_tokens: int
    token_measurement: str
    observed_wall_seconds: float
    monetary_cost: None = None
    pricing_status: str = "unknown"


class QualificationStatus(StrEnum):
    QUALIFIED = "QUALIFIED"
    FAILED = "FAILED"


def suite_fingerprint(suite: EvalSuite) -> str:
    """Bind every policy input, while excluding route identity and observations."""
    return sha256(
        {
            "name": suite.name,
            "version": suite.version,
            "task_kind": suite.task_kind,
            "raw_hash": suite.raw_hash,
            "cases": [{"id": case.id, "raw_hash": case.raw_hash} for case in suite.cases],
            "protocol": [suite.protocol_name, suite.protocol_version, suite.protocol_hash],
            "output_contract": [suite.output_contract, suite.output_schema_hash],
            "required_capabilities": sorted(suite.required_capabilities),
            "sensitivity_ceiling": suite.sensitivity_ceiling,
            "deterministic_scorers": list(suite.deterministic_scorers),
            "reference_scorers": list(suite.reference_scorers),
            "deterministic_all_pass": True,
            "min_reference_pass_rate": suite.min_reference_pass_rate,
            "budget": asdict(suite.budget),
        }
    )


def route_fingerprint(route: CandidateRoute) -> str:
    return sha256(
        {
            "provider": route.provider,
            "model": route.model,
            "model_revision": route.model_revision,
            "task_kind": route.task_kind,
            "capabilities": sorted(route.capabilities),
            "sensitivity_ceiling": route.sensitivity_ceiling,
        }
    )


def derive_qualification(
    deterministic: tuple[ScorerOutcome, ...],
    matching_cases: int,
    total_cases: int,
    minimum: float,
) -> tuple[QualificationStatus, tuple[str, ...]]:
    if total_cases <= 0 or not 0 <= matching_cases <= total_cases:
        raise EvaluationConfigurationError("Reference aggregate is invalid.")
    reasons: list[str] = []
    failed = [outcome for outcome in deterministic if not outcome.passed]
    if failed:
        reasons.append("deterministic_contract_failed")
        if any(outcome.scorer == "deterministic.budget.v1" for outcome in failed):
            reasons.append("budget_exceeded")
    if matching_cases / total_cases < minimum:
        reasons.append("reference_quality_below_threshold")
    status = QualificationStatus.FAILED if reasons else QualificationStatus.QUALIFIED
    return status, tuple(dict.fromkeys(reasons))
