import pytest

from peos.domain.errors import BudgetExceeded
from peos.domain.models.audit import enforce_budget
from peos.domain.models.request import ModelBudget
from peos.domain.models.response import ModelResponse, UsageRecord


def response() -> ModelResponse:
    return ModelResponse(
        "mock",
        "m",
        "1",
        "req",
        "{}",
        {},
        UsageRecord(4, 3, "mock_whitespace_v1", 10, 8),
        "stop",
        None,
    )


def test_budget_limits_fail_closed() -> None:
    with pytest.raises(BudgetExceeded):
        enforce_budget(ModelBudget(), provider_calls=2, context_bytes=1)
    with pytest.raises(BudgetExceeded):
        enforce_budget(ModelBudget(), provider_calls=0, context_bytes=32769)
    with pytest.raises(BudgetExceeded):
        enforce_budget(
            ModelBudget(), provider_calls=1, context_bytes=1, response=response(), wall_seconds=6.0
        )


def test_budget_audit_labels_mock_and_unknown_price() -> None:
    audit = enforce_budget(ModelBudget(), provider_calls=1, context_bytes=1, response=response())
    assert audit["token_measurement"] == "mock_whitespace_v1"
    assert audit["monetary_cost"] is None
    assert audit["pricing_status"] == "unknown"
