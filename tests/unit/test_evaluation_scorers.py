from peos.domain.evaluations import BudgetLimits, ResourceUsage
from peos.domain.evaluations.scorers import budget_score, contract_score, exact_output_score


def usage(**changes: object) -> ResourceUsage:
    values = dict(
        provider_calls=1,
        cache_hit_count=0,
        input_bytes=10,
        output_bytes=10,
        input_tokens=2,
        output_tokens=2,
        token_measurement="mock_whitespace_v1",
        observed_wall_seconds=0.1,
    )
    values.update(changes)
    return ResourceUsage(**values)  # type: ignore[arg-type]


def test_budget_is_a_hard_observed_gate() -> None:
    limit = BudgetLimits(1, 3, 3, 20, 20)
    assert budget_score(usage(), limit).passed
    assert not budget_score(usage(output_tokens=4), limit).passed


def test_exact_reference_uses_expected_bytes_and_shuffled_goldens_fail() -> None:
    actual = ({"summary": "first"}, {"summary": "second"})
    expected = ({"summary": "first"}, {"summary": "second"})
    assert sum(exact_output_score(a, e).passed for a, e in zip(actual, expected, strict=True)) == 2
    shuffled = tuple(reversed(expected))
    assert sum(exact_output_score(a, e).passed for a, e in zip(actual, shuffled, strict=True)) == 0


def test_malformed_summary_fails_contract_even_if_reference_matches() -> None:
    malformed = {"summary": "same"}
    fixture: dict[str, object] = {
        "source_artifact_id": "art_" + "1" * 32,
        "source_revision": "sha256:" + "2" * 64,
    }
    assert exact_output_score(malformed, malformed).passed
    assert not contract_score("summarization", malformed, fixture).passed
