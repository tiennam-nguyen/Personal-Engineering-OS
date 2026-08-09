"""Canonical eval-report-backed authorization for normal model routing."""

from __future__ import annotations

from typing import cast

from peos.domain.errors import EvaluationConfigurationError, RouteQualificationRequired
from peos.domain.evaluations import CandidateRoute, route_fingerprint, suite_fingerprint
from peos.domain.evaluations.report import validate_eval_report
from peos.ports.artifact_repository import ArtifactRepository
from peos.ports.evaluation_suite_repository import EvaluationSuiteRepository
from peos.ports.run_repository import RunRepository


class QualificationService:
    def __init__(
        self, suites: EvaluationSuiteRepository, artifacts: ArtifactRepository, runs: RunRepository
    ) -> None:
        self._suites, self._artifacts, self._runs = suites, artifacts, runs

    def require(self, route: CandidateRoute, protocol_hash: str, output_schema_hash: str) -> None:
        try:
            suite = self._suites.active_for_task(route.task_kind)
        except EvaluationConfigurationError as error:
            raise RouteQualificationRequired(
                f"Route qualification required for task {route.task_kind}."
            ) from error
        identity = (
            route.task_kind,
            route_fingerprint(route),
            suite_fingerprint(suite),
            protocol_hash,
            output_schema_hash,
        )
        reports: list[tuple[str, str, str]] = []
        for stored in self._artifacts.scan():
            artifact = stored.artifact
            if artifact.type != "system.eval_report":
                continue
            try:
                report = validate_eval_report(artifact.payload)
                source_run = str(report["source_run_id"])
                if artifact.provenance.run_id != source_run:
                    continue
                manifest = self._runs.read_manifest(source_run)
                workflow = cast(dict[str, object], manifest.get("workflow"))
                if workflow != {
                    "name": "system.evaluate-model-route",
                    "version": "1.0.0",
                }:
                    continue
                events = self._runs.events(source_run)
                if not events or events[-1].type != "run.succeeded":
                    continue
                outputs = self._runs.read_outputs(source_run)
                suite_data = cast(dict[str, object], report["suite"])
                route_data = cast(dict[str, object], report["route"])
                protocol = cast(dict[str, object], suite_data["protocol_ref"])
                contract = cast(dict[str, object], suite_data["output_contract"])
                candidate = (
                    suite_data["task_kind"],
                    route_data["route_fingerprint"],
                    suite_data["fingerprint"],
                    protocol["sha256"],
                    contract["schema_hash"],
                )
                if (
                    outputs is not None
                    and outputs.get("status") == "SUCCEEDED"
                    and any(
                        isinstance(item, dict)
                        and item.get("id") == artifact.id
                        and item.get("content_hash") == artifact.content_hash
                        for item in cast(list[object], outputs.get("artifacts", []))
                    )
                    and candidate == identity
                ):
                    qualification = cast(dict[str, object], report["qualification"])
                    reports.append((artifact.created_at, artifact.id, str(qualification["status"])))
            except Exception:
                continue
        reports.sort(key=lambda item: (item[0], item[1]))
        if not reports or reports[-1][2] != "QUALIFIED":
            raise RouteQualificationRequired(
                f"Route qualification required for task {route.task_kind}."
            )
