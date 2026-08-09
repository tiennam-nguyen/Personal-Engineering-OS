from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from peos.bootstrap import open_evaluation_workspace, open_workspace
from peos.domain.errors import EvaluationIntegrityError
from peos.domain.evaluations.report import validate_eval_report
from tests.integration.test_evaluation_workflow import workspace


def test_report_tamper_matrix_fails_derivation(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    result = open_evaluation_workspace(root).start(
        "model.summarization.core", "mock", "deterministic-concept-summary-v1", "1"
    )
    artifacts, _ = open_workspace(root)
    payload = artifacts.get(str(result["report_artifact_id"])).artifact.payload
    assert validate_eval_report(payload)["qualification"] == {"status": "QUALIFIED", "reasons": []}
    mutations = (
        ("aggregate", "deterministic_gate", "passed_count"),
        ("aggregate", "reference_quality", "matching_cases"),
        ("aggregate", "resource_usage", "provider_calls"),
        ("aggregate", "resource_usage", "output_tokens"),
        ("qualification", "status"),
    )
    for path in mutations:
        changed = deepcopy(payload)
        assert isinstance(changed, dict)
        if len(path) == 3:
            first = changed[path[0]]
            assert isinstance(first, dict)
            second = first[path[1]]
            assert isinstance(second, dict)
            second[path[2]] = -1
        else:
            value = changed[path[0]]
            assert isinstance(value, dict)
            value[path[1]] = "FAILED"
        with pytest.raises(EvaluationIntegrityError):
            validate_eval_report(changed)


def test_failed_qualification_cannot_be_flipped_to_qualified(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    result = open_evaluation_workspace(root).start(
        "model.summarization.core", "mock", "deterministic-concept-summary-short-v1", "1"
    )
    artifacts, _ = open_workspace(root)
    payload = artifacts.get(str(result["report_artifact_id"])).artifact.payload
    truthful = validate_eval_report(payload)
    assert truthful["qualification"] == {
        "status": "FAILED",
        "reasons": ["reference_quality_below_threshold"],
    }
    changed = deepcopy(truthful)
    qualification = changed["qualification"]
    assert isinstance(qualification, dict)
    qualification["status"] = "QUALIFIED"
    qualification["reasons"] = []

    with pytest.raises(EvaluationIntegrityError):
        validate_eval_report(changed)
