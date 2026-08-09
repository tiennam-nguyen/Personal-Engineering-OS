from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from peos.adapters.filesystem.evaluation_repository import FilesystemEvaluationSuiteRepository
from peos.adapters.filesystem.protocol_repository import FilesystemProtocolRepository
from peos.adapters.filesystem.repository import FilesystemArtifactRepository
from peos.adapters.filesystem.run_repository import FilesystemRunRepository
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.adapters.models.mock import DeterministicMockGateway
from peos.adapters.sqlite.artifact_index import SQLiteArtifactIndex
from peos.application.evaluation_candidates import CandidateCatalog
from peos.application.evaluations import EvaluationService
from peos.application.qualifications import QualificationService
from peos.domain.errors import RouteQualificationRequired
from peos.domain.evaluations import CandidateRoute
from peos.domain.models.request import ModelRequest
from peos.domain.models.response import ModelResponse
from peos.domain.runs.model import canonical_json
from peos.ports.fault_injector import SimulatedInterruption, SingleCheckpointFaultInjector
from tests.integration.test_evaluation_workflow import workspace

ROUTE = CandidateRoute(
    "mock",
    "deterministic-concept-summary-v1",
    "1",
    "summarization",
    frozenset({"structured_output"}),
    "private",
)


def services(root: Path) -> tuple[EvaluationService, QualificationService]:
    store = WorkspaceStore()
    ws = store.open(root)
    artifacts = FilesystemArtifactRepository(ws, store)
    runs = FilesystemRunRepository(ws)
    suites = FilesystemEvaluationSuiteRepository(root)
    evaluation = EvaluationService(
        ws.workspace_id,
        suites,
        FilesystemProtocolRepository(root),
        runs,
        artifacts,
        SQLiteArtifactIndex(ws.index_path),
        CandidateCatalog(DeterministicMockGateway()),
    )
    return evaluation, QualificationService(suites, artifacts, runs)


def identity(root: Path) -> tuple[str, str]:
    suite = FilesystemEvaluationSuiteRepository(root).active_for_task("summarization")
    return suite.protocol_hash, suite.output_schema_hash


def test_unqualified_fails_closed_then_verified_report_authorizes(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    evaluation, qualifications = services(root)
    protocol_hash, schema_hash = identity(root)
    with pytest.raises(RouteQualificationRequired):
        qualifications.require(ROUTE, protocol_hash, schema_hash)
    result = evaluation.start(
        "model.summarization.core", "mock", "deterministic-concept-summary-v1", "1"
    )
    assert result["status"] == "QUALIFIED"
    qualifications.require(ROUTE, protocol_hash, schema_hash)


class WrongSummaryGateway(DeterministicMockGateway):
    def generate(self, request: ModelRequest) -> ModelResponse:
        response = super().generate(request)
        output = dict(response.parsed_output)
        output["summary"] = "A valid but incorrect summary."
        return ModelResponse(
            response.provider,
            response.model,
            response.model_revision,
            response.provider_request_id,
            canonical_json(output).decode(),
            output,
            response.usage,
            response.finish_reason,
            response.raw_response_ref,
        )


def test_latest_failed_report_revokes_previous_qualification(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    evaluation, qualifications = services(root)
    protocol_hash, schema_hash = identity(root)
    assert (
        evaluation.start("model.summarization.core", "mock", ROUTE.model, "1")["status"]
        == "QUALIFIED"
    )
    store = WorkspaceStore()
    ws = store.open(root)
    artifacts = FilesystemArtifactRepository(ws, store)
    failing = EvaluationService(
        ws.workspace_id,
        FilesystemEvaluationSuiteRepository(root),
        FilesystemProtocolRepository(root),
        FilesystemRunRepository(ws),
        artifacts,
        SQLiteArtifactIndex(ws.index_path),
        CandidateCatalog(WrongSummaryGateway()),
    )
    assert failing.start("model.summarization.core", "mock", ROUTE.model, "1")["status"] == "FAILED"
    with pytest.raises(RouteQualificationRequired):
        qualifications.require(ROUTE, protocol_hash, schema_hash)


def test_report_from_cancelled_incomplete_run_cannot_authorize_route(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    store = WorkspaceStore()
    ws = store.open(root)
    artifacts = FilesystemArtifactRepository(ws, store)
    runs = FilesystemRunRepository(ws)
    suites = FilesystemEvaluationSuiteRepository(root)
    interrupted = EvaluationService(
        ws.workspace_id,
        suites,
        FilesystemProtocolRepository(root),
        runs,
        artifacts,
        SQLiteArtifactIndex(ws.index_path),
        CandidateCatalog(DeterministicMockGateway()),
        SingleCheckpointFaultInjector("after_eval_report_canonical_commit"),
    )
    with pytest.raises(SimulatedInterruption):
        interrupted.start("model.summarization.core", "mock", ROUTE.model, "1")
    run_id = next(ws.runs_root.iterdir()).name
    interrupted.cancel(run_id)
    protocol_hash, schema_hash = identity(root)

    with pytest.raises(RouteQualificationRequired):
        QualificationService(suites, artifacts, runs).require(ROUTE, protocol_hash, schema_hash)


def test_protocol_and_output_schema_changes_invalidate_old_qualification(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    evaluation, qualifications = services(root)
    protocol_hash, schema_hash = identity(root)
    assert evaluation.start("model.summarization.core", "mock", ROUTE.model, "1")["status"] == (
        "QUALIFIED"
    )
    qualifications.require(ROUTE, protocol_hash, schema_hash)
    with pytest.raises(RouteQualificationRequired):
        qualifications.require(ROUTE, "sha256:" + "a" * 64, schema_hash)
    with pytest.raises(RouteQualificationRequired):
        qualifications.require(ROUTE, protocol_hash, "sha256:" + "b" * 64)


def test_valid_suite_policy_change_invalidates_old_qualification(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    evaluation, qualifications = services(root)
    protocol_hash, schema_hash = identity(root)
    assert evaluation.start("model.summarization.core", "mock", ROUTE.model, "1")["status"] == (
        "QUALIFIED"
    )
    qualifications.require(ROUTE, protocol_hash, schema_hash)
    suite_path = root / "evals/suites/model.summarization.core/suite.yaml"
    suite_data = yaml.safe_load(suite_path.read_bytes())
    suite_data["thresholds"]["min_reference_pass_rate"] = 0.95
    suite_raw = yaml.safe_dump(suite_data, sort_keys=False).encode()
    suite_path.write_bytes(suite_raw)
    registry_path = root / "evals/registry.yaml"
    registry_data = yaml.safe_load(registry_path.read_bytes())
    registry_data["suites"][0]["sha256"] = "sha256:" + hashlib.sha256(suite_raw).hexdigest()
    registry_path.write_bytes(yaml.safe_dump(registry_data, sort_keys=False).encode())

    with pytest.raises(RouteQualificationRequired):
        services(root)[1].require(ROUTE, protocol_hash, schema_hash)
