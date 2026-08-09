"""Strict canonical evaluation report validation and mechanical re-derivation."""

from __future__ import annotations

from typing import cast

from peos.domain.errors import EvaluationIntegrityError
from peos.domain.evaluations.model import QualificationStatus

REPORT_KEYS = {"suite", "route", "cases", "aggregate", "qualification", "method", "source_run_id"}


def validate_eval_report(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != REPORT_KEYS:
        raise EvaluationIntegrityError("Eval report fields are invalid.")
    suite, route, aggregate, qualification, method = (
        value["suite"],
        value["route"],
        value["aggregate"],
        value["qualification"],
        value["method"],
    )
    if not isinstance(suite, dict) or set(suite) != {
        "name",
        "version",
        "task_kind",
        "fingerprint",
        "protocol_ref",
        "output_contract",
        "scorer_versions",
        "thresholds",
        "budget",
    }:
        raise EvaluationIntegrityError("Eval report suite fields are invalid.")
    if not isinstance(route, dict) or set(route) != {
        "provider",
        "model",
        "model_revision",
        "route_fingerprint",
    }:
        raise EvaluationIntegrityError("Eval report route fields are invalid.")
    if not isinstance(value["cases"], list) or not value["cases"]:
        raise EvaluationIntegrityError("Eval report cases are invalid.")
    cases = value["cases"]
    case_keys = {
        "case_id",
        "frozen_case_hash",
        "request_fingerprint",
        "response_hash",
        "provider_request_id",
        "deterministic_scorers",
        "reference_scorers",
        "usage",
    }
    passed = failed = matching = 0
    deterministic_reasons: list[str] = []
    totals = {
        key: 0
        for key in (
            "provider_calls",
            "cache_hit_count",
            "input_bytes",
            "output_bytes",
            "input_tokens",
            "output_tokens",
        )
    }
    wall = 0.0
    for case in cases:
        if not isinstance(case, dict) or set(case) != case_keys:
            raise EvaluationIntegrityError("Eval case result fields are invalid.")
        deterministic_values = case["deterministic_scorers"]
        reference_values = case["reference_scorers"]
        usage = case["usage"]
        if (
            not isinstance(deterministic_values, list)
            or not isinstance(reference_values, list)
            or not isinstance(usage, dict)
        ):
            raise EvaluationIntegrityError("Eval case scoring evidence is invalid.")
        for outcome in deterministic_values:
            if not isinstance(outcome, dict) or set(outcome) != {
                "scorer",
                "passed",
                "reason_codes",
            }:
                raise EvaluationIntegrityError("Deterministic scorer evidence is invalid.")
            if (
                not isinstance(outcome["scorer"], str)
                or not isinstance(outcome["passed"], bool)
                or not isinstance(outcome["reason_codes"], (list, tuple))
                or not all(isinstance(code, str) for code in outcome["reason_codes"])
            ):
                raise EvaluationIntegrityError("Deterministic scorer evidence is invalid.")
            passed += int(outcome["passed"] is True)
            failed += int(outcome["passed"] is not True)
            deterministic_reasons.extend(cast(list[str] | tuple[str, ...], outcome["reason_codes"]))
        if len(reference_values) != 1 or not isinstance(reference_values[0], dict):
            raise EvaluationIntegrityError("Reference scorer evidence is invalid.")
        matching += int(reference_values[0].get("passed") is True)
        for key in totals:
            observed = usage.get(key)
            if not isinstance(observed, int):
                raise EvaluationIntegrityError("Case resource evidence is invalid.")
            totals[key] += observed
        observed_wall = usage.get("observed_wall_seconds")
        if (
            not isinstance(observed_wall, (int, float))
            or usage.get("token_measurement") != "mock_whitespace_v1"
            or usage.get("monetary_cost") is not None
            or usage.get("pricing_status") != "unknown"
        ):
            raise EvaluationIntegrityError("Case wall-time evidence is invalid.")
        wall += observed_wall
    if not isinstance(aggregate, dict) or set(aggregate) != {
        "deterministic_gate",
        "reference_quality",
        "resource_usage",
    }:
        raise EvaluationIntegrityError("Eval report aggregates are invalid.")
    deterministic = aggregate["deterministic_gate"]
    reference = aggregate["reference_quality"]
    resources = aggregate["resource_usage"]
    if not isinstance(deterministic, dict) or set(deterministic) != {
        "required_scorer_count",
        "passed_count",
        "failed_count",
        "all_required_passed",
        "failure_reason_codes",
    }:
        raise EvaluationIntegrityError("Deterministic aggregate is invalid.")
    if not isinstance(reference, dict) or set(reference) != {
        "matching_cases",
        "total_cases",
        "pass_rate",
        "configured_minimum",
    }:
        raise EvaluationIntegrityError("Reference aggregate is invalid.")
    if not isinstance(resources, dict) or set(resources) != {
        "provider_calls",
        "cache_hit_count",
        "input_bytes",
        "output_bytes",
        "input_tokens",
        "output_tokens",
        "token_measurement",
        "observed_wall_seconds",
        "monetary_cost",
        "pricing_status",
    }:
        raise EvaluationIntegrityError("Resource aggregate is invalid.")
    if (
        resources["cache_hit_count"] != 0
        or resources["monetary_cost"] is not None
        or resources["pricing_status"] != "unknown"
    ):
        raise EvaluationIntegrityError("Eval cache or pricing evidence is invalid.")
    if (
        deterministic["passed_count"] != passed
        or deterministic["failed_count"] != failed
        or deterministic["required_scorer_count"] != passed + failed
        or deterministic["all_required_passed"] is not (failed == 0)
        or deterministic["failure_reason_codes"] != list(dict.fromkeys(deterministic_reasons))
        or reference["matching_cases"] != matching
        or reference["total_cases"] != len(cases)
        or any(resources[key] != total for key, total in totals.items())
        or not isinstance(resources["observed_wall_seconds"], (int, float))
        or abs(resources["observed_wall_seconds"] - wall) > 1e-9
    ):
        raise EvaluationIntegrityError("Eval report aggregate derivation is invalid.")
    if not isinstance(qualification, dict) or set(qualification) != {"status", "reasons"}:
        raise EvaluationIntegrityError("Qualification fields are invalid.")
    matches, total = reference["matching_cases"], reference["total_cases"]
    minimum = reference["configured_minimum"]
    pass_rate = reference["pass_rate"]
    if (
        not isinstance(matches, int)
        or not isinstance(total, int)
        or total <= 0
        or not isinstance(minimum, (int, float))
        or not 0 <= minimum <= 1
        or not isinstance(pass_rate, (int, float))
        or abs(pass_rate - matches / total) > 1e-12
    ):
        raise EvaluationIntegrityError("Reference counts are invalid.")
    derived = deterministic["all_required_passed"] is True and matches / total >= minimum
    expected = QualificationStatus.QUALIFIED.value if derived else QualificationStatus.FAILED.value
    if qualification["status"] != expected:
        raise EvaluationIntegrityError("Qualification is not mechanically derived.")
    if not isinstance(method, dict) or method != {
        "evaluator_version": "1.0.0",
        "cache_policy": "bypass",
        "token_measurement": "mock_whitespace_v1",
    }:
        raise EvaluationIntegrityError("Evaluation method is invalid.")
    return cast(dict[str, object], value)
