from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from peos.adapters.filesystem.evaluation_repository import FilesystemEvaluationSuiteRepository
from peos.domain.errors import EvaluationConfigurationError, EvaluationIntegrityError


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def install(root: Path, *, bad_case_hash: bool = False) -> None:
    case = (
        b"schema_version: 1\nid: summary.basic\ntask_kind: summarization\n"
        b"input_fixture:\n  source_artifact_id: art_11111111111111111111111111111111\n"
        b"  source_revision: sha256:22222222222222222222222222222222"
        b"22222222222222222222222222222222\n"
        b"expected:\n  summary: faithful\ntags:\n  - core\n"
    )
    case_path = root / "evals/suites/summary/cases/basic.yaml"
    case_path.parent.mkdir(parents=True)
    case_path.write_bytes(case)
    case_hash = "sha256:" + "0" * 64 if bad_case_hash else digest(case)
    suite = (
        "schema_version: 1\nname: model.summarization.core\nversion: 1.0.0\n"
        "task_kind: summarization\nprotocol:\n  name: sample.concept-summary\n  version: 1.0.0\n"
        f"  sha256: {'sha256:' + '3' * 64}\noutput_contract:\n  name: sample.concept_summary.v1\n"
        f"  schema_hash: {'sha256:' + '4' * 64}\nrequired_capabilities:\n  - structured_output\n"
        "sensitivity_ceiling: private\nscorers:\n  deterministic:\n"
        "    - deterministic.contract.v1\n"
        "    - deterministic.budget.v1\n  reference:\n    - reference.exact_output.v1\n"
        "thresholds:\n  deterministic_all_pass: true\n  min_reference_pass_rate: 1.0\n"
        "budget:\n  max_provider_calls_per_case: 1\n  max_input_tokens_per_case: 100\n"
        "  max_output_tokens_per_case: 100\n  max_input_bytes_per_case: 1000\n"
        "  max_output_bytes_per_case: 1000\ncases:\n"
        "  - path: evals/suites/summary/cases/basic.yaml\n"
        f"    sha256: {case_hash}\n"
    ).encode()
    suite_path = root / "evals/suites/summary/suite.yaml"
    suite_path.write_bytes(suite)
    registry = (
        "schema_version: 1\nsuites:\n  - name: model.summarization.core\n"
        "    version: 1.0.0\n    task_kind: summarization\n"
        "    path: evals/suites/summary/suite.yaml\n"
        f"    sha256: {digest(suite)}\n    status: active\n    qualification_suite: true\n"
    ).encode()
    (root / "evals/registry.yaml").write_bytes(registry)


def test_strict_repository_loads_raw_hashes_and_orders(tmp_path: Path) -> None:
    install(tmp_path)
    suite = FilesystemEvaluationSuiteRepository(tmp_path).active_for_task("summarization")
    assert suite.name == "model.summarization.core"
    assert suite.cases[0].id == "summary.basic"


def test_case_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    install(tmp_path, bad_case_hash=True)
    with pytest.raises(EvaluationIntegrityError):
        FilesystemEvaluationSuiteRepository(tmp_path).list_active()


def test_traversal_and_noncanonical_newline_fail(tmp_path: Path) -> None:
    install(tmp_path)
    registry = tmp_path / "evals/registry.yaml"
    registry.write_text(
        registry.read_text().replace("evals/suites/summary/suite.yaml", "../suite.yaml")
    )
    with pytest.raises(EvaluationConfigurationError):
        FilesystemEvaluationSuiteRepository(tmp_path).list_active()
    registry.write_bytes(b"schema_version: 1\r\nsuites: []\r\n")
    with pytest.raises(EvaluationConfigurationError):
        FilesystemEvaluationSuiteRepository(tmp_path).list_active()
