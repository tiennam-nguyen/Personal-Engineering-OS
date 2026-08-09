"""Frozen evaluation workflow, canonical report creation, and evidence comparison."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import cast

from peos.application.evaluation_candidates import CandidateCatalog, request_for_case
from peos.domain.artifacts.model import Artifact, Author, Provenance
from peos.domain.errors import (
    DuplicateArtifactId,
    EvaluationIntegrityError,
    EvaluationNotComparable,
    ModelCallOutcomeUnknown,
    ModelCapabilityMismatch,
    TerminalRunError,
)
from peos.domain.evaluations import (
    BudgetLimits,
    CandidateRoute,
    EvalCase,
    EvalSuite,
    ResourceUsage,
    ScorerOutcome,
    derive_qualification,
    route_fingerprint,
    suite_fingerprint,
)
from peos.domain.evaluations.report import validate_eval_report
from peos.domain.evaluations.scorers import budget_score, contract_score, exact_output_score
from peos.domain.models.audit import response_hash
from peos.domain.models.request import ProtocolRef
from peos.domain.models.response import ModelResponse, UsageRecord
from peos.domain.runs.events import event_mapping
from peos.domain.runs.model import Event, deterministic_step_id, sha256
from peos.ports.artifact_index import ArtifactIndex
from peos.ports.artifact_repository import ArtifactRepository
from peos.ports.evaluation_suite_repository import EvaluationSuiteRepository
from peos.ports.fault_injector import FaultInjector, NoOpFaultInjector
from peos.ports.model_gateway import ModelGateway
from peos.ports.protocol_repository import ProtocolRepository
from peos.ports.run_repository import RunRepository


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


class EvaluationService:
    def __init__(
        self,
        workspace_id: str,
        suites: EvaluationSuiteRepository,
        protocols: ProtocolRepository,
        runs: RunRepository,
        artifacts: ArtifactRepository,
        index: ArtifactIndex,
        candidates: CandidateCatalog,
        faults: FaultInjector | None = None,
    ) -> None:
        self._workspace_id, self._suites, self._protocols = workspace_id, suites, protocols
        self._runs, self._artifacts, self._index, self._candidates = (
            runs,
            artifacts,
            index,
            candidates,
        )
        self._faults = faults or NoOpFaultInjector()

    def start(
        self,
        suite_name: str,
        provider: str,
        model: str,
        revision: str,
        stop_after_step: str | None = None,
    ) -> dict[str, object]:
        suite = self._suites.get(suite_name)
        route, gateway = self._candidates.resolve(provider, model, revision)
        if (
            route.task_kind != suite.task_kind
            or not suite.required_capabilities <= route.capabilities
        ):
            raise ModelCapabilityMismatch("Evaluation candidate is incompatible with frozen suite.")
        order = {"public": 0, "private": 1, "confidential": 2}
        if order[suite.sensitivity_ceiling] > order[route.sensitivity_ceiling]:
            raise ModelCapabilityMismatch("Evaluation sensitivity exceeds candidate ceiling.")
        protocol = self._protocols.get(suite.protocol_name, suite.protocol_version)
        if protocol.sha256 != suite.protocol_hash:
            raise EvaluationIntegrityError("Suite protocol hash differs from canonical protocol.")
        frozen_suite = self._frozen_suite(suite)
        suite_fp, route_fp = suite_fingerprint(suite), route_fingerprint(route)
        run_id = "run_" + uuid.uuid4().hex
        steps = [
            self._step(run_id, 1, "freeze-eval-suite", "REVERSIBLE_WRITE"),
            self._step(run_id, 2, "execute-eval-cases", "EXTERNAL_CALL"),
            self._step(run_id, 3, "commit-eval-report", "REVERSIBLE_WRITE"),
        ]
        inputs = {
            "schema_version": 1,
            "suite": frozen_suite,
            "suite_fingerprint": suite_fp,
            "route": asdict(route) | {"capabilities": sorted(route.capabilities)},
            "route_fingerprint": route_fp,
            "protocol_content": protocol.content,
        }
        manifest = {
            "schema_version": 1,
            "run_id": run_id,
            "workflow": {"name": "system.evaluate-model-route", "version": "1.0.0"},
            "created_at": _now(),
            "input_manifest_hash": sha256(inputs),
            "steps": steps,
            "protocol_hashes": [
                {"name": protocol.name, "version": protocol.version, "sha256": protocol.sha256}
            ],
        }
        self._runs.create(manifest, inputs)
        self._event(
            run_id,
            "run.created",
            None,
            {"workflow_name": "system.evaluate-model-route", "workflow_version": "1.0.0"},
        )
        self._event(
            run_id, "run.planned", None, {"step_count": 3, "input_manifest_hash": sha256(inputs)}
        )
        self._event(run_id, "run.started", None, {})
        first = steps[0]
        self._begin(run_id, first)
        frozen = self._evidence(
            run_id,
            str(first["step_id"]),
            "evaluation/frozen-suite.json",
            "frozen_eval_suite",
            inputs,
        )
        self._complete(run_id, first, frozen, [])
        self._faults.checkpoint("after_eval_suite_frozen")
        if stop_after_step == "freeze-eval-suite":
            return self.inspect(run_id)
        second = steps[1]
        self._begin(run_id, second)
        protocol_ev = self._evidence(
            run_id,
            str(second["step_id"]),
            "evaluation/protocol-snapshot.json",
            "protocol_snapshot",
            {
                "name": protocol.name,
                "version": protocol.version,
                "sha256": protocol.sha256,
                "content": protocol.content,
            },
        )
        self._event(
            run_id,
            "protocol.loaded",
            str(second["step_id"]),
            {
                "call_id": "evaluation-suite",
                "evidence_path": "evidence/evaluation/protocol-snapshot.json",
                "content_hash": protocol_ev["content_hash"],
            },
        )
        results: list[dict[str, object]] = []
        for ordinal, case in enumerate(suite.cases, 1):
            request = request_for_case(
                case.input_fixture,
                route,
                ProtocolRef(protocol.name, protocol.version, protocol.sha256),
                protocol.content,
            )
            call_id = f"eval-{ordinal:04d}-{request.fingerprint()[7:19]}"
            base = f"evaluation/cases/{ordinal:04d}-{case.id}"
            request_data: dict[str, object] = {
                "call_id": call_id,
                "case_id": case.id,
                "request_fingerprint": request.fingerprint(),
                "task_kind": request.task_kind,
                "route": {"provider": provider, "model": model, "model_revision": revision},
                "cache_policy": "bypass",
                "output_schema_hash": sha256(request.output_schema),
            }
            request_ev = self._evidence(
                run_id,
                str(second["step_id"]),
                f"{base}/request-audit.json",
                "model_request_audit",
                request_data,
            )
            self._event(
                run_id,
                "context.compiled",
                str(second["step_id"]),
                {
                    "call_id": call_id,
                    "evidence_path": f"evidence/{base}/request-audit.json",
                    "content_hash": request_ev["content_hash"],
                },
            )
            self._event(
                run_id,
                "model.request_compiled",
                str(second["step_id"]),
                {
                    "call_id": call_id,
                    "evidence_path": f"evidence/{base}/request-audit.json",
                    "content_hash": request_ev["content_hash"],
                },
            )
            self._event(
                run_id,
                "model.cache_miss",
                str(second["step_id"]),
                {
                    "call_id": call_id,
                    "cache_key": sha256({"eval": request.fingerprint(), "route": route_fp}),
                    "bypassed": True,
                },
            )
            self._event(
                run_id,
                "model.call_started",
                str(second["step_id"]),
                {
                    "call_id": call_id,
                    "provider": provider,
                    "model": model,
                    "model_revision": revision,
                },
            )
            self._faults.checkpoint(f"after_eval_case_{ordinal}_call_started")
            started = time.monotonic()
            response = gateway.generate(request)
            wall = time.monotonic() - started
            if (response.provider, response.model, response.model_revision) != (
                provider,
                model,
                revision,
            ):
                raise EvaluationIntegrityError("Candidate returned a different route identity.")
            self._event(
                run_id,
                "model.call_completed",
                str(second["step_id"]),
                {"call_id": call_id, "provider_request_id": response.provider_request_id},
            )
            usage = ResourceUsage(
                1,
                0,
                response.usage.input_bytes,
                response.usage.output_bytes,
                response.usage.input_tokens,
                response.usage.output_tokens,
                response.usage.token_measurement,
                wall,
            )
            response_data = {
                "provider": response.provider,
                "model": response.model,
                "model_revision": response.model_revision,
                "provider_request_id": response.provider_request_id,
                "content": response.content,
                "parsed_output": response.parsed_output,
                "usage": asdict(response.usage),
                "finish_reason": response.finish_reason,
                "response_hash": response_hash(response),
                "cache_hit": False,
            }
            response_ev = self._evidence(
                run_id,
                str(second["step_id"]),
                f"{base}/response-audit.json",
                "model_response_audit",
                response_data,
            )
            self._event(
                run_id,
                "model.response_validated",
                str(second["step_id"]),
                {
                    "call_id": call_id,
                    "evidence_path": f"evidence/{base}/response-audit.json",
                    "content_hash": response_ev["content_hash"],
                    "response_hash": response_data["response_hash"],
                },
            )
            budget = budget_score(usage, suite.budget)
            budget_ev = self._evidence(
                run_id,
                str(second["step_id"]),
                f"{base}/budget-audit.json",
                "model_budget_audit",
                {"usage": asdict(usage), "outcome": asdict(budget)},
            )
            self._event(
                run_id,
                "model.budget_recorded",
                str(second["step_id"]),
                {
                    "call_id": call_id,
                    "evidence_path": f"evidence/{base}/budget-audit.json",
                    "content_hash": budget_ev["content_hash"],
                    "passed": budget.passed,
                },
            )
            self._faults.checkpoint(f"after_eval_case_{ordinal}_audited")
            results.append(
                {
                    "case": case,
                    "request": request_data,
                    "response": response_data,
                    "usage": usage,
                    "budget": budget,
                }
            )
        staged = self._evidence(
            run_id,
            str(second["step_id"]),
            "evaluation/case-results.json",
            "eval_case_results",
            {"cases": [self._result_evidence(item) for item in results]},
        )
        self._complete(run_id, second, staged, [])
        self._faults.checkpoint("after_all_eval_cases_audited")
        if stop_after_step == "execute-eval-cases":
            return self.inspect(run_id)
        third = steps[2]
        self._begin(run_id, third)
        report = self._report(run_id, suite, route, suite_fp, route_fp, results)
        validate_eval_report(report)
        created = _now()
        artifact = Artifact(
            "art_" + uuid.uuid4().hex,
            "system.eval_report",
            1,
            f"Evaluation: {suite.name} / {model}@{revision}",
            "accepted",
            self._workspace_id,
            created,
            created,
            (Author("system", "peos"),),
            "private",
            ("evaluation", suite.task_kind),
            (),
            Provenance("system", run_id, ()),
            None,
            "# Evaluation Report\n\nDeterministic qualification evidence.\n",
            report,
        )
        stored = self._artifacts.save(artifact)
        self._index.upsert(stored)
        self._event(
            run_id,
            "artifact.canonical_committed",
            str(third["step_id"]),
            {
                "artifact_id": stored.artifact.id,
                "canonical_path": stored.canonical_path,
                "content_hash": stored.artifact.content_hash,
            },
        )
        self._event(
            run_id,
            "artifact.projected",
            str(third["step_id"]),
            {"artifact_id": stored.artifact.id, "content_hash": stored.artifact.content_hash},
        )
        self._faults.checkpoint("after_eval_report_canonical_commit")
        report_ev = self._evidence(
            run_id,
            str(third["step_id"]),
            "evaluation/report-verification.json",
            "eval_report_verification",
            {
                "valid": True,
                "artifact_id": stored.artifact.id,
                "content_hash": stored.artifact.content_hash,
            },
        )
        self._complete(
            run_id,
            third,
            report_ev,
            [
                {
                    "kind": "artifact",
                    "id": stored.artifact.id,
                    "content_hash": stored.artifact.content_hash,
                }
            ],
        )
        outputs = {
            "schema_version": 1,
            "run_id": run_id,
            "status": "SUCCEEDED",
            "completed_at": _now(),
            "artifacts": [
                {
                    "id": stored.artifact.id,
                    "type": "system.eval_report",
                    "canonical_path": stored.canonical_path,
                    "content_hash": stored.artifact.content_hash,
                }
            ],
            "partial_artifacts": [],
        }
        self._event(run_id, "run.verification_started", None, {"committed_steps": 3})
        self._runs.write_outputs(run_id, outputs)
        self._faults.checkpoint("after_eval_outputs_written")
        self._event(
            run_id, "run.succeeded", None, {"outputs_path": "outputs.json", "artifact_count": 1}
        )
        qualification = cast(dict[str, object], report["qualification"])
        aggregate = cast(dict[str, object], report["aggregate"])
        return {
            "eval_run_id": run_id,
            "report_artifact_id": stored.artifact.id,
            "report_revision": stored.artifact.content_hash,
            "suite_fingerprint": suite_fp,
            "route_fingerprint": route_fp,
            **qualification,
            "deterministic_gate": aggregate["deterministic_gate"],
            "reference_quality": aggregate["reference_quality"],
            "resource_usage": aggregate["resource_usage"],
        }

    def compare(self, run_a: str, run_b: str) -> dict[str, object]:
        a, b = self._report_for_run(run_a), self._report_for_run(run_b)
        a_suite = cast(dict[str, object], a["suite"])
        b_suite = cast(dict[str, object], b["suite"])
        if (
            a_suite["task_kind"] != b_suite["task_kind"]
            or a_suite["fingerprint"] != b_suite["fingerprint"]
        ):
            raise EvaluationNotComparable(
                "Evaluation runs do not share task and suite fingerprint."
            )
        return {
            "suite_fingerprint": a_suite["fingerprint"],
            "candidates": [self._comparison_side(a), self._comparison_side(b)],
            "deltas": self._resource_deltas(a, b),
        }

    def inspect(self, run_id: str) -> dict[str, object]:
        manifest = self._runs.read_manifest(run_id)
        workflow = cast(dict[str, object], manifest.get("workflow"))
        if workflow.get("name") != "system.evaluate-model-route":
            raise EvaluationIntegrityError("Run is not an evaluation workflow.")
        events = self._runs.events(run_id)
        outputs = self._runs.read_outputs(run_id)
        terminal = next(
            (event.type for event in reversed(events) if event.type.startswith("run.")),
            "run.started",
        )
        state = (
            "SUCCEEDED"
            if terminal == "run.succeeded"
            else "CANCELLED"
            if terminal == "run.cancelled"
            else "FAILED"
            if terminal == "run.failed"
            else "RUNNING"
        )
        return {
            "run_id": run_id,
            "workflow": workflow["name"],
            "state": state,
            "committed_steps": sum(event.type == "step.committed" for event in events),
            "produced_artifacts": [] if outputs is None else outputs.get("artifacts", []),
        }

    def resume(self, run_id: str) -> dict[str, object]:
        view = self.inspect(run_id)
        if view["state"] == "SUCCEEDED":
            return view
        if view["state"] == "CANCELLED":
            raise TerminalRunError("Cancelled evaluation cannot resume.")
        inputs = self._runs.read_inputs(run_id)
        if sha256(inputs) != self._runs.read_manifest(run_id)["input_manifest_hash"]:
            raise EvaluationIntegrityError("Frozen evaluation inputs changed.")
        suite = self._suite_from_frozen(cast(dict[str, object], inputs["suite"]))
        route_data = cast(dict[str, object], inputs["route"])
        capabilities = route_data["capabilities"]
        if not isinstance(capabilities, list):
            raise EvaluationIntegrityError("Frozen candidate capabilities are invalid.")
        route = CandidateRoute(
            str(route_data["provider"]),
            str(route_data["model"]),
            str(route_data["model_revision"]),
            str(route_data["task_kind"]),
            frozenset(str(item) for item in capabilities),
            str(route_data["sensitivity_ceiling"]),
        )
        _, gateway = self._candidates.resolve(route.provider, route.model, route.model_revision)
        manifest = self._runs.read_manifest(run_id)
        steps = cast(list[dict[str, object]], manifest["steps"])
        self._event(
            run_id,
            "run.recovering",
            None,
            {"last_sequence": len(self._runs.events(run_id)), "frontier": "evaluation"},
        )
        self._event(
            run_id, "run.resumed", None, {"next_step": self.inspect(run_id)["committed_steps"]}
        )
        results = self._resume_cases(
            run_id,
            steps[1],
            suite,
            route,
            gateway,
            str(inputs["protocol_content"]),
        )
        if not self._committed(run_id, str(steps[1]["step_id"])):
            staged = self._evidence(
                run_id,
                str(steps[1]["step_id"]),
                "evaluation/case-results.json",
                "eval_case_results",
                {"cases": [self._result_evidence(item) for item in results]},
            )
            self._complete(run_id, steps[1], staged, [])
        return self._finish_run(
            run_id,
            steps[2],
            suite,
            route,
            str(inputs["suite_fingerprint"]),
            str(inputs["route_fingerprint"]),
            results,
        )

    def cancel(self, run_id: str) -> dict[str, object]:
        view = self.inspect(run_id)
        if view["state"] == "CANCELLED":
            return view
        if view["state"] in {"SUCCEEDED", "FAILED"}:
            raise TerminalRunError("Terminal evaluation cannot be cancelled.")
        self._event(
            run_id,
            "run.cancelled",
            None,
            {
                "frontier": "evaluation",
                "partial_artifact_count": len(cast(list[object], view["produced_artifacts"])),
            },
        )
        return self.inspect(run_id)

    def verify(self, run_id: str) -> dict[str, object]:
        view = self.inspect(run_id)
        if view["state"] == "SUCCEEDED":
            self._report_for_run(run_id)
        return {
            "run_id": run_id,
            "valid": True,
            "workflow": "system.evaluate-model-route",
            "read_only": True,
        }

    def _report_for_run(self, run_id: str) -> dict[str, object]:
        outputs = self._runs.read_outputs(run_id)
        if not outputs or outputs.get("status") != "SUCCEEDED":
            raise EvaluationNotComparable("Input is not a succeeded evaluation run.")
        refs = outputs.get("artifacts")
        if (
            not isinstance(refs, list)
            or len(refs) != 1
            or not isinstance(refs[0], dict)
            or refs[0].get("type") != "system.eval_report"
        ):
            raise EvaluationNotComparable("Input did not produce one eval report.")
        stored = self._artifacts.verify(str(refs[0]["canonical_path"]))
        if (
            refs[0].get("id") != stored.artifact.id
            or refs[0].get("content_hash") != stored.artifact.content_hash
            or stored.artifact.provenance.run_id != run_id
        ):
            raise EvaluationIntegrityError("Eval report output reference is invalid.")
        report = validate_eval_report(stored.artifact.payload)
        inputs = self._runs.read_inputs(run_id)
        manifest = self._runs.read_manifest(run_id)
        if sha256(inputs) != manifest["input_manifest_hash"]:
            raise EvaluationIntegrityError("Frozen evaluation inputs changed.")
        suite = self._suite_from_frozen(cast(dict[str, object], inputs["suite"]))
        route_data = cast(dict[str, object], inputs["route"])
        route = CandidateRoute(
            str(route_data["provider"]),
            str(route_data["model"]),
            str(route_data["model_revision"]),
            str(route_data["task_kind"]),
            frozenset(cast(list[str], route_data["capabilities"])),
            str(route_data["sensitivity_ceiling"]),
        )
        expected_suite_fp = suite_fingerprint(suite)
        expected_route_fp = route_fingerprint(route)
        if (
            inputs["suite_fingerprint"] != expected_suite_fp
            or inputs["route_fingerprint"] != expected_route_fp
        ):
            raise EvaluationIntegrityError("Frozen evaluation fingerprints changed.")
        events = self._runs.events(run_id)
        if sum(event.type == "model.response_validated" for event in events) != len(suite.cases):
            raise EvaluationIntegrityError("Evaluation response audit set is incomplete.")
        steps = cast(list[dict[str, object]], manifest["steps"])
        _, gateway = self._candidates.resolve(route.provider, route.model, route.model_revision)
        results = self._resume_cases(
            run_id,
            steps[1],
            suite,
            route,
            gateway,
            str(inputs["protocol_content"]),
        )
        expected = self._report(run_id, suite, route, expected_suite_fp, expected_route_fp, results)
        if sha256(report) != sha256(expected):
            raise EvaluationIntegrityError("Eval report differs from durable run evidence.")
        return report

    @staticmethod
    def _comparison_side(report: dict[str, object]) -> dict[str, object]:
        aggregate = report["aggregate"]
        assert isinstance(aggregate, dict)
        return {
            "route": report["route"],
            "qualification": report["qualification"],
            "deterministic_gate": aggregate["deterministic_gate"],
            "reference_quality": aggregate["reference_quality"],
            "resource_usage": aggregate["resource_usage"],
        }

    @staticmethod
    def _resource_deltas(a: dict[str, object], b: dict[str, object]) -> dict[str, object]:
        aa, bb = a["aggregate"], b["aggregate"]
        assert isinstance(aa, dict) and isinstance(bb, dict)
        ar, br = aa["resource_usage"], bb["resource_usage"]
        assert isinstance(ar, dict) and isinstance(br, dict)
        fields = (
            "provider_calls",
            "input_bytes",
            "output_bytes",
            "input_tokens",
            "output_tokens",
            "observed_wall_seconds",
        )
        result: dict[str, object] = {}
        for field in fields:
            left, right = ar[field], br[field]
            if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
                raise EvaluationIntegrityError("Comparison resource evidence is invalid.")
            result[field] = right - left
        return result

    def _resume_cases(
        self,
        run_id: str,
        step: dict[str, object],
        suite: EvalSuite,
        route: CandidateRoute,
        gateway: ModelGateway,
        protocol_content: str,
    ) -> list[dict[str, object]]:
        step_id = str(step["step_id"])
        events = self._runs.events(run_id)
        if not any(event.type == "step.created" and event.step_id == step_id for event in events):
            self._begin(run_id, step)
            protocol_ev = self._evidence(
                run_id,
                step_id,
                "evaluation/protocol-snapshot.json",
                "protocol_snapshot",
                {
                    "name": suite.protocol_name,
                    "version": suite.protocol_version,
                    "sha256": suite.protocol_hash,
                    "content": protocol_content,
                },
            )
            self._event(
                run_id,
                "protocol.loaded",
                step_id,
                {
                    "call_id": "evaluation-suite",
                    "evidence_path": "evidence/evaluation/protocol-snapshot.json",
                    "content_hash": protocol_ev["content_hash"],
                },
            )
        results: list[dict[str, object]] = []
        protocol = ProtocolRef(suite.protocol_name, suite.protocol_version, suite.protocol_hash)
        for ordinal, case in enumerate(suite.cases, 1):
            request = request_for_case(case.input_fixture, route, protocol, protocol_content)
            call_id = f"eval-{ordinal:04d}-{request.fingerprint()[7:19]}"
            base = f"evaluation/cases/{ordinal:04d}-{case.id}"
            call_events = [
                event
                for event in self._runs.events(run_id)
                if event.payload.get("call_id") == call_id
            ]
            validated = next(
                (event for event in call_events if event.type == "model.response_validated"), None
            )
            if validated is not None:
                response_envelope = self._runs.read_evidence(run_id, f"{base}/response-audit.json")
                budget_envelope = self._runs.read_evidence(run_id, f"{base}/budget-audit.json")
                request_envelope = self._runs.read_evidence(run_id, f"{base}/request-audit.json")
                response = cast(dict[str, object], response_envelope["data"])
                budget_data = cast(dict[str, object], budget_envelope["data"])
                usage_data = cast(dict[str, object], budget_data["usage"])
                usage = ResourceUsage(
                    int(cast(int, usage_data["provider_calls"])),
                    int(cast(int, usage_data["cache_hit_count"])),
                    int(cast(int, usage_data["input_bytes"])),
                    int(cast(int, usage_data["output_bytes"])),
                    int(cast(int, usage_data["input_tokens"])),
                    int(cast(int, usage_data["output_tokens"])),
                    str(usage_data["token_measurement"]),
                    float(cast(float, usage_data["observed_wall_seconds"])),
                    None,
                    str(usage_data["pricing_status"]),
                )
                outcome = cast(dict[str, object], budget_data["outcome"])
                budget = ScorerOutcome(
                    str(outcome["scorer"]),
                    bool(outcome["passed"]),
                    tuple(cast(list[str], outcome["reason_codes"])),
                )
                request_data = cast(dict[str, object], request_envelope["data"])
                response_usage = cast(dict[str, object], response["usage"])
                audited_response = ModelResponse(
                    str(response["provider"]),
                    str(response["model"]),
                    str(response["model_revision"]),
                    str(response["provider_request_id"]),
                    str(response["content"]),
                    cast(dict[str, object], response["parsed_output"]),
                    UsageRecord(
                        int(cast(int, response_usage["input_tokens"])),
                        int(cast(int, response_usage["output_tokens"])),
                        str(response_usage["token_measurement"]),
                        int(cast(int, response_usage["input_bytes"])),
                        int(cast(int, response_usage["output_bytes"])),
                    ),
                    str(response["finish_reason"]),
                    cast(str | None, response.get("raw_response_ref")),
                )
                expected_route = {
                    "provider": route.provider,
                    "model": route.model,
                    "model_revision": route.model_revision,
                }
                budget_event = next(
                    (event for event in call_events if event.type == "model.budget_recorded"), None
                )
                if (
                    request_data["request_fingerprint"] != request.fingerprint()
                    or request_data["route"] != expected_route
                    or request_data["output_schema_hash"] != sha256(request.output_schema)
                    or (
                        response["provider"],
                        response["model"],
                        response["model_revision"],
                    )
                    != (route.provider, route.model, route.model_revision)
                    or response["response_hash"] != response_hash(audited_response)
                    or response["response_hash"] != validated.payload["response_hash"]
                    or validated.payload.get("content_hash") != response_envelope["content_hash"]
                    or validated.payload.get("evidence_path")
                    != f"evidence/{base}/response-audit.json"
                    or budget != budget_score(usage, suite.budget)
                    or not any(event.type == "model.call_completed" for event in call_events)
                    or budget_event is None
                    or budget_event.payload.get("content_hash") != budget_envelope["content_hash"]
                    or budget_event.payload.get("evidence_path")
                    != f"evidence/{base}/budget-audit.json"
                ):
                    raise EvaluationIntegrityError(
                        "Completed eval case audit conflicts with frozen request."
                    )
                results.append(
                    {
                        "case": case,
                        "request": request_data,
                        "response": response,
                        "usage": usage,
                        "budget": budget,
                    }
                )
                continue
            if any(event.type == "model.call_started" for event in call_events):
                raise ModelCallOutcomeUnknown("Evaluation candidate call outcome is unknown.")
            new_request_data: dict[str, object] = {
                "call_id": call_id,
                "case_id": case.id,
                "request_fingerprint": request.fingerprint(),
                "task_kind": request.task_kind,
                "route": {
                    "provider": route.provider,
                    "model": route.model,
                    "model_revision": route.model_revision,
                },
                "cache_policy": "bypass",
                "output_schema_hash": sha256(request.output_schema),
            }
            request_ev = self._evidence(
                run_id,
                step_id,
                f"{base}/request-audit.json",
                "model_request_audit",
                new_request_data,
            )
            common = {
                "call_id": call_id,
                "evidence_path": f"evidence/{base}/request-audit.json",
                "content_hash": request_ev["content_hash"],
            }
            self._event(run_id, "context.compiled", step_id, common)
            self._event(run_id, "model.request_compiled", step_id, common)
            self._event(
                run_id,
                "model.cache_miss",
                step_id,
                {
                    "call_id": call_id,
                    "cache_key": sha256(
                        {"eval": request.fingerprint(), "route": route_fingerprint(route)}
                    ),
                    "bypassed": True,
                },
            )
            self._event(
                run_id,
                "model.call_started",
                step_id,
                {
                    "call_id": call_id,
                    "provider": route.provider,
                    "model": route.model,
                    "model_revision": route.model_revision,
                },
            )
            self._faults.checkpoint(f"after_eval_case_{ordinal}_call_started")
            started = time.monotonic()
            generated = gateway.generate(request)
            wall = time.monotonic() - started
            self._event(
                run_id,
                "model.call_completed",
                step_id,
                {"call_id": call_id, "provider_request_id": generated.provider_request_id},
            )
            usage = ResourceUsage(
                1,
                0,
                generated.usage.input_bytes,
                generated.usage.output_bytes,
                generated.usage.input_tokens,
                generated.usage.output_tokens,
                generated.usage.token_measurement,
                wall,
            )
            new_response: dict[str, object] = {
                "provider": generated.provider,
                "model": generated.model,
                "model_revision": generated.model_revision,
                "provider_request_id": generated.provider_request_id,
                "content": generated.content,
                "parsed_output": generated.parsed_output,
                "usage": asdict(generated.usage),
                "finish_reason": generated.finish_reason,
                "response_hash": response_hash(generated),
                "cache_hit": False,
            }
            response_ev = self._evidence(
                run_id,
                step_id,
                f"{base}/response-audit.json",
                "model_response_audit",
                new_response,
            )
            self._event(
                run_id,
                "model.response_validated",
                step_id,
                {
                    "call_id": call_id,
                    "evidence_path": f"evidence/{base}/response-audit.json",
                    "content_hash": response_ev["content_hash"],
                    "response_hash": new_response["response_hash"],
                },
            )
            budget = budget_score(usage, suite.budget)
            budget_ev = self._evidence(
                run_id,
                step_id,
                f"{base}/budget-audit.json",
                "model_budget_audit",
                {"usage": asdict(usage), "outcome": asdict(budget)},
            )
            self._event(
                run_id,
                "model.budget_recorded",
                step_id,
                {
                    "call_id": call_id,
                    "evidence_path": f"evidence/{base}/budget-audit.json",
                    "content_hash": budget_ev["content_hash"],
                    "passed": budget.passed,
                },
            )
            results.append(
                {
                    "case": case,
                    "request": new_request_data,
                    "response": new_response,
                    "usage": usage,
                    "budget": budget,
                }
            )
        return results

    @staticmethod
    def _result_evidence(item: dict[str, object]) -> dict[str, object]:
        request = cast(dict[str, object], item["request"])
        return {
            "case_id": cast(EvalCase, item["case"]).id,
            "call_id": request["call_id"],
            "frozen_case_hash": cast(EvalCase, item["case"]).raw_hash,
        }

    @staticmethod
    def _suite_from_frozen(data: dict[str, object]) -> EvalSuite:
        cases_list: list[EvalCase] = []
        for raw_item in cast(list[object], data["cases"]):
            item = cast(dict[str, object], raw_item)
            cases_list.append(
                EvalCase(
                    str(item["id"]),
                    str(item["task_kind"]),
                    cast(dict[str, object], item["input_fixture"]),
                    cast(dict[str, object], item["expected"]),
                    tuple(cast(list[str], item["tags"])),
                    str(item["raw_hash"]),
                )
            )
        cases = tuple(cases_list)
        budget = BudgetLimits(**cast(dict[str, int], data["budget"]))
        return EvalSuite(
            str(data["name"]),
            str(data["version"]),
            str(data["task_kind"]),
            str(data["raw_hash"]),
            str(data["protocol_name"]),
            str(data["protocol_version"]),
            str(data["protocol_hash"]),
            str(data["output_contract"]),
            str(data["output_schema_hash"]),
            frozenset(cast(list[str], data["required_capabilities"])),
            str(data["sensitivity_ceiling"]),
            tuple(cast(list[str], data["deterministic_scorers"])),
            tuple(cast(list[str], data["reference_scorers"])),
            float(cast(float, data["min_reference_pass_rate"])),
            budget,
            cases,
        )

    def _committed(self, run_id: str, step_id: str) -> bool:
        return any(
            event.type == "step.committed" and event.step_id == step_id
            for event in self._runs.events(run_id)
        )

    def _finish_run(
        self,
        run_id: str,
        step: dict[str, object],
        suite: EvalSuite,
        route: CandidateRoute,
        suite_fp: str,
        route_fp: str,
        results: list[dict[str, object]],
    ) -> dict[str, object]:
        step_id = str(step["step_id"])
        events = self._runs.events(run_id)
        canonical = next(
            (
                event
                for event in events
                if event.type == "artifact.canonical_committed" and event.step_id == step_id
            ),
            None,
        )
        if canonical is None:
            if not any(
                event.type == "step.created" and event.step_id == step_id for event in events
            ):
                self._begin(run_id, step)
            report = self._report(run_id, suite, route, suite_fp, route_fp, results)
            validate_eval_report(report)
            created = _now()
            artifact = Artifact(
                "art_" + uuid.uuid4().hex,
                "system.eval_report",
                1,
                f"Evaluation: {suite.name} / {route.model}@{route.model_revision}",
                "accepted",
                self._workspace_id,
                created,
                created,
                (Author("system", "peos"),),
                "private",
                ("evaluation", suite.task_kind),
                (),
                Provenance("system", run_id, ()),
                None,
                "# Evaluation Report\n\nDeterministic qualification evidence.\n",
                report,
            )
            stored = self._artifacts.save(artifact)
            self._event(
                run_id,
                "artifact.canonical_committed",
                step_id,
                {
                    "artifact_id": stored.artifact.id,
                    "canonical_path": stored.canonical_path,
                    "content_hash": stored.artifact.content_hash,
                },
            )
        else:
            stored = self._artifacts.verify(str(canonical.payload["canonical_path"]))
        try:
            self._index.upsert(stored)
        except DuplicateArtifactId:
            projected = self._index.get(stored.artifact.id)
            if projected.artifact.content_hash != stored.artifact.content_hash:
                raise
        if not any(
            event.type == "artifact.projected" and event.step_id == step_id
            for event in self._runs.events(run_id)
        ):
            self._event(
                run_id,
                "artifact.projected",
                step_id,
                {"artifact_id": stored.artifact.id, "content_hash": stored.artifact.content_hash},
            )
        if not self._committed(run_id, step_id):
            report_ev = self._evidence(
                run_id,
                step_id,
                "evaluation/report-verification.json",
                "eval_report_verification",
                {
                    "valid": True,
                    "artifact_id": stored.artifact.id,
                    "content_hash": stored.artifact.content_hash,
                },
            )
            self._complete(
                run_id,
                step,
                report_ev,
                [
                    {
                        "kind": "artifact",
                        "id": stored.artifact.id,
                        "content_hash": stored.artifact.content_hash,
                    }
                ],
            )
        outputs = self._runs.read_outputs(run_id)
        if outputs is None:
            outputs = {
                "schema_version": 1,
                "run_id": run_id,
                "status": "SUCCEEDED",
                "completed_at": _now(),
                "artifacts": [
                    {
                        "id": stored.artifact.id,
                        "type": "system.eval_report",
                        "canonical_path": stored.canonical_path,
                        "content_hash": stored.artifact.content_hash,
                    }
                ],
                "partial_artifacts": [],
            }
            self._runs.write_outputs(run_id, outputs)
        if not any(event.type == "run.verification_started" for event in self._runs.events(run_id)):
            self._event(run_id, "run.verification_started", None, {"committed_steps": 3})
        if not any(event.type == "run.succeeded" for event in self._runs.events(run_id)):
            self._event(
                run_id, "run.succeeded", None, {"outputs_path": "outputs.json", "artifact_count": 1}
            )
        return self.inspect(run_id)

    def _report(
        self,
        run_id: str,
        suite: EvalSuite,
        route: CandidateRoute,
        suite_fp: str,
        route_fp: str,
        results: list[dict[str, object]],
    ) -> dict[str, object]:
        cases: list[dict[str, object]] = []
        deterministic: list[ScorerOutcome] = []
        matches = 0
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
        for item in results:
            case = cast(EvalCase, item["case"])
            response = cast(dict[str, object], item["response"])
            usage = cast(ResourceUsage, item["usage"])
            budget = cast(ScorerOutcome, item["budget"])
            request = cast(dict[str, object], item["request"])
            contract = contract_score(
                suite.task_kind, response["parsed_output"], case.input_fixture
            )
            reference = exact_output_score(response["parsed_output"], case.expected)
            deterministic.extend((contract, budget))
            matches += int(reference.passed)
            for key in totals:
                totals[key] += getattr(usage, key)
            wall += usage.observed_wall_seconds
            cases.append(
                {
                    "case_id": case.id,
                    "frozen_case_hash": case.raw_hash,
                    "request_fingerprint": request["request_fingerprint"],
                    "response_hash": response["response_hash"],
                    "provider_request_id": response["provider_request_id"],
                    "deterministic_scorers": [asdict(contract), asdict(budget)],
                    "reference_scorers": [asdict(reference)],
                    "usage": asdict(usage),
                }
            )
        status, reasons = derive_qualification(
            tuple(deterministic), matches, len(results), suite.min_reference_pass_rate
        )
        failed = sum(not outcome.passed for outcome in deterministic)
        resources = totals | {
            "token_measurement": "mock_whitespace_v1",
            "observed_wall_seconds": wall,
            "monetary_cost": None,
            "pricing_status": "unknown",
        }
        return {
            "suite": {
                "name": suite.name,
                "version": suite.version,
                "task_kind": suite.task_kind,
                "fingerprint": suite_fp,
                "protocol_ref": {
                    "name": suite.protocol_name,
                    "version": suite.protocol_version,
                    "sha256": suite.protocol_hash,
                },
                "output_contract": {
                    "name": suite.output_contract,
                    "schema_hash": suite.output_schema_hash,
                },
                "scorer_versions": [*suite.deterministic_scorers, *suite.reference_scorers],
                "thresholds": {
                    "deterministic_all_pass": True,
                    "min_reference_pass_rate": suite.min_reference_pass_rate,
                },
                "budget": asdict(suite.budget),
            },
            "route": {
                "provider": route.provider,
                "model": route.model,
                "model_revision": route.model_revision,
                "route_fingerprint": route_fp,
            },
            "cases": cases,
            "aggregate": {
                "deterministic_gate": {
                    "required_scorer_count": len(deterministic),
                    "passed_count": len(deterministic) - failed,
                    "failed_count": failed,
                    "all_required_passed": failed == 0,
                    "failure_reason_codes": list(
                        dict.fromkeys(
                            code for outcome in deterministic for code in outcome.reason_codes
                        )
                    ),
                },
                "reference_quality": {
                    "matching_cases": matches,
                    "total_cases": len(results),
                    "pass_rate": matches / len(results),
                    "configured_minimum": suite.min_reference_pass_rate,
                },
                "resource_usage": resources,
            },
            "qualification": {"status": status.value, "reasons": list(reasons)},
            "method": {
                "evaluator_version": "1.0.0",
                "cache_policy": "bypass",
                "token_measurement": "mock_whitespace_v1",
            },
            "source_run_id": run_id,
        }

    @staticmethod
    def _frozen_suite(suite: EvalSuite) -> dict[str, object]:
        return asdict(suite) | {
            "required_capabilities": sorted(suite.required_capabilities),
            "cases": [asdict(case) for case in suite.cases],
        }

    @staticmethod
    def _step(run_id: str, ordinal: int, name: str, side_effect: str) -> dict[str, object]:
        return {
            "ordinal": ordinal,
            "name": name,
            "version": "1.0.0",
            "side_effect": side_effect,
            "max_attempts": 1,
            "max_output_bytes": 1048576,
            "step_id": deterministic_step_id(run_id, ordinal, name, "1.0.0"),
        }

    def _begin(self, run_id: str, step: dict[str, object]) -> None:
        step_id = str(step["step_id"])
        self._event(
            run_id,
            "step.created",
            step_id,
            {key: step[key] for key in ("ordinal", "name", "version", "side_effect")},
        )
        self._event(run_id, "step.inputs_resolved", step_id, {"input_refs": []})
        self._event(run_id, "step.prepared", step_id, {"attempt": 1})
        self._event(run_id, "step.execution_started", step_id, {"attempt": 1})

    def _complete(
        self,
        run_id: str,
        step: dict[str, object],
        evidence: dict[str, object],
        refs: list[dict[str, object]],
    ) -> None:
        step_id, name = str(step["step_id"]), str(step["name"])
        path = (
            "evaluation/frozen-suite.json"
            if name == "freeze-eval-suite"
            else "evaluation/case-results.json"
            if name == "execute-eval-cases"
            else "evaluation/report-verification.json"
        )
        payload = {"evidence_path": f"evidence/{path}", "content_hash": evidence["content_hash"]}
        self._event(run_id, "step.output_staged", step_id, payload)
        self._event(
            run_id,
            "step.verification_started",
            step_id,
            {"verifier": f"verify_{name}", "version": "1.0.0"},
        )
        self._event(run_id, "step.verification_completed", step_id, {"passed": True, **payload})
        self._event(run_id, "step.committed", step_id, {"output_refs": refs})

    def _evidence(
        self, run_id: str, step_id: str, name: str, kind: str, data: dict[str, object]
    ) -> dict[str, object]:
        self._runs.write_evidence(
            run_id,
            name,
            {"schema_version": 1, "run_id": run_id, "step_id": step_id, "kind": kind, "data": data},
        )
        return self._runs.read_evidence(run_id, name)

    def _event(
        self, run_id: str, type_: str, step_id: str | None, payload: dict[str, object]
    ) -> None:
        events = self._runs.events(run_id)
        bare = Event(
            1,
            "evt_" + uuid.uuid4().hex,
            run_id,
            step_id,
            len(events) + 1,
            _now(),
            type_,
            {"kind": "system", "id": "peos"},
            payload,
            events[-1].event_hash if events else None,
            "",
        )
        self._runs.append(
            run_id,
            Event(
                **{**bare.__dict__, "event_hash": sha256(event_mapping(bare, include_hash=False))}
            ),
        )
