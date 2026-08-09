from __future__ import annotations

import pytest

from peos.domain.errors import LearningInputInvalid
from peos.domain.learning.model import parse_goal_input


def test_goal_contract_rejects_missing_and_non_positive_values() -> None:
    with pytest.raises(LearningInputInvalid):
        parse_goal_input({"schema_version": 1})
