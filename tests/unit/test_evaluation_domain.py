from __future__ import annotations

from dataclasses import replace

import pytest

from peos.domain.errors import EvaluationConfigurationError
from peos.domain.evaluations import (
    BudgetLimits,
    CandidateRoute,
    EvalCase,
    EvalSuite,
    QualificationStatus,
    ScorerOutcome,
    derive_qualification,
    route_fingerprint,
    suite_fingerprint,
)


def suite() -> EvalSuite:
    case = EvalCase(
        "case.one", "summarization", {"body": "x"}, {"summary": "x"}, (), "sha256:" + "1" * 64
    )
    return EvalSuite(
        "model.summarization.core",
        "1.0.0",
        "summarization",
        "sha256:" + "2" * 64,
        "sample.concept-summary",
        "1.0.0",
        "sha256:" + "3" * 64,
        "sample.concept_summary.v1",
        "sha256:" + "4" * 64,
        frozenset({"structured_output"}),
        "private",
        ("deterministic.contract.v1", "deterministic.budget.v1"),
        ("reference.exact_output.v1",),
        1.0,
        BudgetLimits(1, 100, 100, 100, 100),
        (case,),
    )


def test_suite_fingerprint_binds_every_policy_category() -> None:
    original = suite()
    mutations = (
        replace(original, raw_hash="sha256:" + "5" * 64),
        replace(original, protocol_hash="sha256:" + "5" * 64),
        replace(original, output_schema_hash="sha256:" + "5" * 64),
        replace(original, min_reference_pass_rate=0.5),
        replace(original, deterministic_scorers=("deterministic.contract.v1",)),
        replace(original, budget=BudgetLimits(1, 99, 100, 100, 100)),
        replace(original, cases=(replace(original.cases[0], raw_hash="sha256:" + "5" * 64),)),
    )
    assert all(suite_fingerprint(item) != suite_fingerprint(original) for item in mutations)


def test_route_fingerprint_is_revision_specific() -> None:
    route = CandidateRoute(
        "mock", "model", "1", "summarization", frozenset({"structured_output"}), "private"
    )
    assert route_fingerprint(route) == route_fingerprint(route)
    assert route_fingerprint(route) != route_fingerprint(replace(route, model_revision="2"))


def test_qualification_formula_keeps_hard_gates_distinct() -> None:
    passed = (ScorerOutcome("deterministic.contract.v1", True, ()),)
    assert derive_qualification(passed, 1, 1, 1.0)[0] is QualificationStatus.QUALIFIED
    budget = (ScorerOutcome("deterministic.budget.v1", False, ("output_tokens_exceeded",)),)
    status, reasons = derive_qualification(budget, 1, 1, 1.0)
    assert status is QualificationStatus.FAILED
    assert "budget_exceeded" in reasons


def test_invalid_threshold_duplicate_cases_and_unknown_scorer_fail() -> None:
    original = suite()
    with pytest.raises(EvaluationConfigurationError):
        replace(original, min_reference_pass_rate=1.1)
    with pytest.raises(EvaluationConfigurationError):
        replace(original, cases=(original.cases[0], original.cases[0]))
    with pytest.raises(EvaluationConfigurationError):
        replace(original, deterministic_scorers=("arbitrary.plugin",))
