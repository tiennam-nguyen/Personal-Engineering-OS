"""Run start, resume, inspection, verification, and cancellation."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict
from datetime import UTC, datetime

from peos.application.modeling import ModelCallService
from peos.domain.artifacts.model import Artifact, StoredArtifact
from peos.domain.errors import (
    ArtifactNotFound,
    DuplicateArtifactId,
    IndexDivergenceError,
    InputRevisionMismatch,
    ModelCallOutcomeUnknown,
    RunConflictError,
    TerminalRunError,
)
from peos.domain.models.request import ModelBudget
from peos.domain.runs.events import event_mapping, verify_events
from peos.domain.runs.model import Event, RunState, deterministic_step_id, sha256
from peos.ports.artifact_index import ArtifactIndex
from peos.ports.artifact_repository import ArtifactRepository
from peos.ports.fault_injector import FaultInjector, NoOpFaultInjector
from peos.ports.run_repository import RunRepository
from peos.workflows.mock_summary import prepare_summary
from peos.workflows.registry import get
from peos.workflows.sample import artifact_data, prepare, verify_prepared


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class RunService:
    def __init__(
        self,
        runs: RunRepository,
        artifacts: ArtifactRepository,
        index: ArtifactIndex,
        workspace_id: str,
        fault_injector: FaultInjector | None = None,
        modeling: ModelCallService | None = None,
    ) -> None:
        self._runs, self._artifacts, self._index, self._workspace_id = (
            runs,
            artifacts,
            index,
            workspace_id,
        )
        self._faults = fault_injector or NoOpFaultInjector()
        self._modeling = modeling

    def start(
        self,
        workflow: str,
        input_id: str,
        stop_after_step: str | None = None,
        no_cache: bool = False,
    ) -> dict[str, object]:
        if workflow == "sample.mock-summarize-concept":
            return self._start_model(input_id, stop_after_step, no_cache)
        if no_cache:
            raise RunConflictError("--no-cache is valid only for the model workflow.")
        definition = get(workflow)
        source = self._lookup(input_id)
        run_id = "run_" + uuid.uuid4().hex
        created = _now()
        inputs = {
            "schema_version": 1,
            "artifacts": [
                {
                    "id": source.artifact.id,
                    "type": source.artifact.type,
                    "schema_version": source.artifact.schema_version,
                    "canonical_path": source.canonical_path,
                    "content_hash": source.artifact.content_hash,
                }
            ],
        }
        steps = [
            {
                "ordinal": step.ordinal,
                "step_id": deterministic_step_id(run_id, step.ordinal, step.name, step.version),
                "name": step.name,
                "version": step.version,
                "side_effect": step.side_effect,
                "max_attempts": 1,
                "timeout_seconds": None,
                "max_output_bytes": step.max_output_bytes,
            }
            for step in definition.steps
        ]
        manifest = {
            "schema_version": 1,
            "run_id": run_id,
            "workspace_id": self._workspace_id,
            "workflow": {"name": definition.name, "version": definition.version},
            "created_at": created,
            "input_manifest_hash": sha256(inputs),
            "steps": steps,
            "configuration_snapshot": {
                "workspace_schema_version": 1,
                "run_root": ".peos/runs",
                "single_writer": True,
            },
            "protocol_hashes": [],
            "cancellation_behavior": "between_invocations",
        }
        self._runs.create(manifest, inputs)
        self._event(
            run_id,
            "run.created",
            None,
            {"workflow_name": definition.name, "workflow_version": definition.version},
        )
        self._event(
            run_id,
            "run.planned",
            None,
            {"step_count": 2, "input_manifest_hash": manifest["input_manifest_hash"]},
        )
        self._event(run_id, "run.started", None, {})
        return self._execute(run_id, stop_after_step)

    def resume(self, run_id: str) -> dict[str, object]:
        self._validate(run_id)
        if self._state(run_id) in {RunState.SUCCEEDED, RunState.CANCELLED, RunState.FAILED}:
            raise RunConflictError("Terminal run cannot resume.")
        events = self._runs.events(run_id)
        self._event(
            run_id,
            "run.recovering",
            None,
            {"last_sequence": events[-1].sequence, "frontier": self._frontier(run_id)},
        )
        self._event(
            run_id,
            "run.resumed",
            None,
            {"next_step": self.inspect(run_id)["next_step"]},
        )
        return self._execute(run_id)

    def inspect(self, run_id: str) -> dict[str, object]:
        manifest = self._runs.read_manifest(run_id)
        events = self._runs.events(run_id)
        return self._view(manifest, events)

    def cancel(self, run_id: str) -> dict[str, object]:
        self._validate(run_id)
        state = self._state(run_id)
        if state == RunState.CANCELLED:
            return {"run_id": run_id, "state": "CANCELLED", "terminal": True}
        if state in {RunState.SUCCEEDED, RunState.FAILED}:
            raise TerminalRunError("Terminal run cannot be cancelled.")
        partial = []
        for event in self._runs.events(run_id):
            if event.type == "artifact.canonical_committed":
                partial.append(
                    {
                        "id": self._artifact_id_from_path(str(event.payload["canonical_path"])),
                        "canonical_path": event.payload["canonical_path"],
                        "content_hash": event.payload["content_hash"],
                    }
                )
        self._runs.write_outputs(
            run_id,
            {
                "schema_version": 1,
                "run_id": run_id,
                "status": "CANCELLED",
                "completed_at": _now(),
                "artifacts": [],
                "partial_artifacts": partial,
            },
        )
        self._event(
            run_id,
            "run.cancelled",
            None,
            {"frontier": self._frontier(run_id), "partial_artifact_count": len(partial)},
        )
        return {"run_id": run_id, "state": "CANCELLED", "terminal": True}

    def verify(self, run_id: str) -> dict[str, object]:
        self._validate(run_id)
        return {"run_id": run_id, "valid": True, "state": self._state(run_id).value}

    def _execute(self, run_id: str, stop: str | None = None) -> dict[str, object]:
        manifest = self._runs.read_manifest(run_id)
        workflow = manifest.get("workflow")
        if isinstance(workflow, dict) and workflow.get("name") == "sample.mock-summarize-concept":
            return self._execute_model(run_id, stop)
        source = self._frozen_input(run_id, manifest)
        steps = manifest["steps"]
        assert isinstance(steps, list)
        first, second = steps
        assert isinstance(first, dict) and isinstance(second, dict)
        first_id = str(first["step_id"])
        second_id = str(second["step_id"])
        if not self._has(run_id, "step.created", first_id):
            self._event(
                run_id,
                "step.created",
                first_id,
                {
                    "ordinal": 1,
                    "name": first["name"],
                    "version": first["version"],
                    "side_effect": first["side_effect"],
                },
            )
        if not self._has(run_id, "step.inputs_resolved", first_id):
            self._event(
                run_id,
                "step.inputs_resolved",
                first_id,
                {
                    "input_refs": [
                        {
                            "kind": "artifact",
                            "id": source.artifact.id,
                            "content_hash": source.artifact.content_hash,
                        }
                    ]
                },
            )
        if not self._has(run_id, "step.prepared", first_id):
            self._event(run_id, "step.prepared", first_id, {"attempt": 1})
        if not self._has(run_id, "step.execution_started", first_id):
            self._event(run_id, "step.execution_started", str(first["step_id"]), {"attempt": 1})
        prepared_data = artifact_data(prepare(source.artifact, run_id, str(manifest["created_at"])))
        if not self._has(run_id, "step.output_staged", first_id):
            envelope = {
                "schema_version": 1,
                "run_id": run_id,
                "step_id": first["step_id"],
                "step_name": first["name"],
                "kind": "prepared_artifact",
                "data": prepared_data,
            }
            self._runs.write_evidence(run_id, "step-01-prepared-artifact.json", envelope)
            prepared_evidence = self._runs.read_evidence(run_id, "step-01-prepared-artifact.json")
            self._event(
                run_id,
                "step.output_staged",
                str(first["step_id"]),
                {
                    "evidence_path": "evidence/step-01-prepared-artifact.json",
                    "content_hash": prepared_evidence["content_hash"],
                },
            )
            self._faults.checkpoint("after_step_1_output_staged")
        else:
            evidence = self._runs.read_evidence(run_id, "step-01-prepared-artifact.json")
            if evidence.get("data") != prepared_data:
                raise RunConflictError(
                    "Prepared artifact evidence conflicts with deterministic output."
                )
            prepared_evidence = evidence
        if not self._has(run_id, "step.verification_completed", first_id):
            if not self._has(run_id, "step.verification_started", first_id):
                self._event(
                    run_id,
                    "step.verification_started",
                    first_id,
                    {"verifier": "verify_prepared", "version": "1.0.0"},
                )
            verify_prepared(source.artifact, run_id, str(manifest["created_at"]), prepared_data)
            self._runs.write_evidence(
                run_id,
                "step-01-verification.json",
                {
                    "schema_version": 1,
                    "run_id": run_id,
                    "step_id": first["step_id"],
                    "step_name": first["name"],
                    "kind": "verification_result",
                    "data": {"valid": True},
                },
            )
            verified_evidence = self._runs.read_evidence(run_id, "step-01-verification.json")
            self._event(
                run_id,
                "step.verification_completed",
                first_id,
                {
                    "passed": True,
                    "evidence_path": "evidence/step-01-verification.json",
                    "content_hash": verified_evidence["content_hash"],
                },
            )
            self._faults.checkpoint("after_step_1_verification_completed")
        if not self._has(run_id, "step.committed", first_id):
            self._event(
                run_id,
                "step.committed",
                first_id,
                {
                    "output_refs": [
                        {
                            "kind": "evidence",
                            "id": "step-01-prepared-artifact",
                            "content_hash": prepared_evidence["content_hash"],
                        }
                    ]
                },
            )
            self._faults.checkpoint("after_step_1_committed")
        if stop == "prepare-derived-concept":
            return self.inspect(run_id) | {"stopped_after_step": "prepare-derived-concept"}
        evidence = self._runs.read_evidence(run_id, "step-01-prepared-artifact.json")
        data = evidence["data"]
        assert isinstance(data, dict)
        prepared = verify_prepared(source.artifact, run_id, str(manifest["created_at"]), data)
        if not self._has(run_id, "step.created", second_id):
            self._event(
                run_id,
                "step.created",
                second_id,
                {
                    "ordinal": 2,
                    "name": second["name"],
                    "version": second["version"],
                    "side_effect": second["side_effect"],
                },
            )
        if not self._has(run_id, "step.inputs_resolved", second_id):
            self._event(
                run_id,
                "step.inputs_resolved",
                second_id,
                {
                    "input_refs": [
                        {
                            "kind": "step_output",
                            "id": "step-01-prepared-artifact",
                            "content_hash": evidence["content_hash"],
                        }
                    ]
                },
            )
        if not self._has(run_id, "step.prepared", second_id):
            self._event(run_id, "step.prepared", second_id, {"attempt": 1})
        if not self._has(run_id, "step.execution_started", second_id):
            self._event(run_id, "step.execution_started", str(second["step_id"]), {"attempt": 1})
        if not self._has(run_id, "step.output_staged", second_id):
            self._runs.write_evidence(
                run_id,
                "step-02-staged-artifact.json",
                {
                    "schema_version": 1,
                    "run_id": run_id,
                    "step_id": second["step_id"],
                    "step_name": second["name"],
                    "kind": "staged_artifact",
                    "data": data,
                },
            )
            staged_evidence = self._runs.read_evidence(run_id, "step-02-staged-artifact.json")
            self._event(
                run_id,
                "step.output_staged",
                second_id,
                {
                    "evidence_path": "evidence/step-02-staged-artifact.json",
                    "content_hash": staged_evidence["content_hash"],
                },
            )
            self._faults.checkpoint("after_step_2_output_staged")
        else:
            staged = self._runs.read_evidence(run_id, "step-02-staged-artifact.json")
            if staged.get("data") != data:
                raise RunConflictError("Staged artifact evidence conflicts with prepared evidence.")
        if not self._has(run_id, "step.commit_started", second_id):
            self._event(run_id, "step.commit_started", second_id, {"output_id": prepared.id})
            self._faults.checkpoint("after_step_2_commit_started")
        canonical_path = f"artifacts/knowledge/{prepared.id}.md"
        if not self._has(run_id, "artifact.canonical_committed", second_id):
            try:
                stored = self._artifacts.save(prepared)
            except DuplicateArtifactId:
                stored = self._artifacts.verify(canonical_path)
                if (
                    artifact_data(Artifact(**{**stored.artifact.__dict__, "content_hash": None}))
                    != data
                ):
                    raise RunConflictError("Existing deterministic artifact conflicts.")
            self._event(
                run_id,
                "artifact.canonical_committed",
                str(second["step_id"]),
                {
                    "artifact_id": stored.artifact.id,
                    "canonical_path": stored.canonical_path,
                    "content_hash": stored.artifact.content_hash,
                },
            )
            self._faults.checkpoint("after_artifact_canonical_committed")
        else:
            stored = self._artifacts.verify(canonical_path)
            if (
                artifact_data(Artifact(**{**stored.artifact.__dict__, "content_hash": None}))
                != data
            ):
                raise RunConflictError(
                    "Committed canonical artifact conflicts with prepared evidence."
                )
        if not self._has(run_id, "artifact.projected", second_id):
            try:
                self._index.upsert(stored)
            except DuplicateArtifactId:
                projected = self._index.get(stored.artifact.id)
                if (
                    projected.canonical_path != stored.canonical_path
                    or projected.artifact.content_hash != stored.artifact.content_hash
                ):
                    raise IndexDivergenceError("Existing artifact projection conflicts.")
            self._event(
                run_id,
                "artifact.projected",
                second_id,
                {"artifact_id": stored.artifact.id, "content_hash": stored.artifact.content_hash},
            )
            self._faults.checkpoint("after_artifact_projected")
        else:
            projected = self._index.get(stored.artifact.id)
            if (
                projected.canonical_path != stored.canonical_path
                or projected.artifact.content_hash != stored.artifact.content_hash
                or projected.artifact.workspace_id != stored.artifact.workspace_id
            ):
                raise IndexDivergenceError("Recorded artifact projection conflicts.")
        if not self._has(run_id, "step.verification_completed", second_id):
            if not self._has(run_id, "step.verification_started", second_id):
                self._event(
                    run_id,
                    "step.verification_started",
                    second_id,
                    {"verifier": "verify_committed_artifact", "version": "1.0.0"},
                )
            self._runs.write_evidence(
                run_id,
                "step-02-verification.json",
                {
                    "schema_version": 1,
                    "run_id": run_id,
                    "step_id": second["step_id"],
                    "step_name": second["name"],
                    "kind": "verification_result",
                    "data": {"valid": True, "artifact_id": stored.artifact.id},
                },
            )
            verified_evidence = self._runs.read_evidence(run_id, "step-02-verification.json")
            self._event(
                run_id,
                "step.verification_completed",
                second_id,
                {
                    "passed": True,
                    "evidence_path": "evidence/step-02-verification.json",
                    "content_hash": verified_evidence["content_hash"],
                },
            )
        if not self._has(run_id, "step.committed", second_id):
            self._event(
                run_id,
                "step.committed",
                second_id,
                {
                    "output_refs": [
                        {
                            "kind": "artifact",
                            "id": stored.artifact.id,
                            "content_hash": stored.artifact.content_hash,
                        }
                    ]
                },
            )
            self._faults.checkpoint("after_step_2_committed")
        if not self._has(run_id, "run.verification_started", None):
            self._event(run_id, "run.verification_started", None, {"committed_steps": 2})
        output_id = prepare(source.artifact, run_id, str(manifest["created_at"])).id
        produced = self._artifacts.verify(f"artifacts/knowledge/{output_id}.md")
        expected_outputs = {
            "schema_version": 1,
            "run_id": run_id,
            "status": "SUCCEEDED",
            "completed_at": _now(),
            "artifacts": [
                {
                    "id": produced.artifact.id,
                    "type": produced.artifact.type,
                    "canonical_path": produced.canonical_path,
                    "content_hash": produced.artifact.content_hash,
                }
            ],
            "partial_artifacts": [],
        }
        existing_outputs = self._runs.read_outputs(run_id)
        if existing_outputs is None:
            self._runs.write_outputs(run_id, expected_outputs)
            self._faults.checkpoint("after_outputs_written")
        elif {
            key: existing_outputs.get(key)
            for key in ("schema_version", "run_id", "status", "artifacts", "partial_artifacts")
        } != {
            key: expected_outputs.get(key)
            for key in ("schema_version", "run_id", "status", "artifacts", "partial_artifacts")
        }:
            raise RunConflictError("Existing outputs manifest conflicts with verified output.")
        if not self._has(run_id, "run.succeeded", None):
            self._event(
                run_id, "run.succeeded", None, {"outputs_path": "outputs.json", "artifact_count": 1}
            )
        return self.inspect(run_id)

    def _start_model(
        self, input_id: str, stop_after_step: str | None, no_cache: bool
    ) -> dict[str, object]:
        if self._modeling is None:
            raise RunConflictError("Model workflow is not configured.")
        source = self._lookup(input_id)
        protocol = self._modeling.protocol_for_start(source.artifact.sensitivity)
        definition = get("sample.mock-summarize-concept")
        run_id = "run_" + uuid.uuid4().hex
        created = _now()
        inputs = {
            "schema_version": 1,
            "artifacts": [
                {
                    "id": source.artifact.id,
                    "type": source.artifact.type,
                    "schema_version": source.artifact.schema_version,
                    "canonical_path": source.canonical_path,
                    "content_hash": source.artifact.content_hash,
                }
            ],
        }
        steps = [
            {
                "ordinal": step.ordinal,
                "step_id": deterministic_step_id(run_id, step.ordinal, step.name, step.version),
                "name": step.name,
                "version": step.version,
                "side_effect": step.side_effect,
                "max_attempts": 1,
                "timeout_seconds": None,
                "max_output_bytes": step.max_output_bytes,
            }
            for step in definition.steps
        ]
        budget = ModelBudget()
        manifest = {
            "schema_version": 1,
            "run_id": run_id,
            "workspace_id": self._workspace_id,
            "workflow": {"name": definition.name, "version": definition.version},
            "created_at": created,
            "input_manifest_hash": sha256(inputs),
            "steps": steps,
            "configuration_snapshot": {
                "workspace_schema_version": 1,
                "run_root": ".peos/runs",
                "single_writer": True,
                "model": {
                    "route": {
                        "provider": "mock",
                        "model": "deterministic-concept-summary-v1",
                        "model_revision": "1",
                    },
                    "budget": asdict(budget),
                    "cache_policy": "bypass" if no_cache else "use",
                },
            },
            "protocol_hashes": [
                {"name": protocol.name, "version": protocol.version, "sha256": protocol.sha256}
            ],
            "cancellation_behavior": "between_invocations",
        }
        self._runs.create(manifest, inputs)
        self._event(
            run_id,
            "run.created",
            None,
            {"workflow_name": definition.name, "workflow_version": definition.version},
        )
        self._event(
            run_id,
            "run.planned",
            None,
            {"step_count": 2, "input_manifest_hash": manifest["input_manifest_hash"]},
        )
        self._event(run_id, "run.started", None, {})
        return self._execute_model(run_id, stop_after_step)

    def _execute_model(self, run_id: str, stop: str | None = None) -> dict[str, object]:
        if self._modeling is None:
            raise RunConflictError("Model workflow is not configured.")
        manifest = self._runs.read_manifest(run_id)
        source = self._frozen_input(run_id, manifest)
        steps = manifest["steps"]
        assert isinstance(steps, list)
        first, second = steps
        assert isinstance(first, dict) and isinstance(second, dict)
        first_id = str(first["step_id"])
        call_id = "call_" + hashlib.sha256(f"{run_id}:{first_id}:1".encode()).hexdigest()[:32]
        if not self._has(run_id, "step.created", first_id):
            self._event(
                run_id,
                "step.created",
                first_id,
                {
                    "ordinal": 1,
                    "name": first["name"],
                    "version": first["version"],
                    "side_effect": first["side_effect"],
                },
            )
        if not self._has(run_id, "step.inputs_resolved", first_id):
            self._event(
                run_id,
                "step.inputs_resolved",
                first_id,
                {
                    "input_refs": [
                        {
                            "kind": "artifact",
                            "id": source.artifact.id,
                            "content_hash": source.artifact.content_hash,
                        }
                    ]
                },
            )
        if not self._has(run_id, "step.prepared", first_id):
            self._event(run_id, "step.prepared", first_id, {"attempt": 1})
        if not self._has(run_id, "step.execution_started", first_id):
            self._event(run_id, "step.execution_started", first_id, {"attempt": 1})
        prepared_name = "step-01-prepared-artifact.json"
        if self._has(run_id, "model.call_started", first_id) and not self._has(
            run_id, "model.call_completed", first_id
        ):
            raise ModelCallOutcomeUnknown(
                "Model call outcome is unknown; automatic retry is forbidden."
            )
        if self._has(run_id, "model.response_validated", first_id):
            response = self._runs.read_evidence(
                run_id, f"model-calls/{call_id}/response-audit.json"
            )
            response_data = response.get("data")
            if not isinstance(response_data, dict) or not isinstance(
                response_data.get("parsed_output"), dict
            ):
                raise RunConflictError("Durable response audit is invalid.")
            parsed = response_data["parsed_output"]
        elif not self._has(run_id, "step.committed", first_id):
            config = manifest["configuration_snapshot"]
            assert isinstance(config, dict) and isinstance(config.get("model"), dict)
            model_config = config["model"]
            frozen = manifest["protocol_hashes"]
            assert isinstance(frozen, list) and len(frozen) == 1 and isinstance(frozen[0], dict)
            budget_value = model_config["budget"]
            assert isinstance(budget_value, dict)

            def write(name: str, envelope: dict[str, object]) -> dict[str, object]:
                full = {
                    "schema_version": 1,
                    "run_id": run_id,
                    "step_id": first_id,
                    "step_name": first["name"],
                    **envelope,
                }
                self._runs.write_evidence(run_id, name, full)
                return self._runs.read_evidence(run_id, name)

            result = self._modeling.execute(
                run_id=run_id,
                call_id=call_id,
                source_id=source.artifact.id,
                sensitivity=source.artifact.sensitivity,
                budget=ModelBudget(**budget_value),
                cache_policy=str(model_config["cache_policy"]),
                frozen_protocol=frozen[0],
                write_evidence=write,
                emit=lambda event, payload: self._event(run_id, event, first_id, payload),
            )
            parsed = result["parsed_output"]
            assert isinstance(parsed, dict)
            self._faults.checkpoint("after_model_response_audited")
        else:
            prepared_envelope = self._runs.read_evidence(run_id, prepared_name)
            prepared_data = prepared_envelope["data"]
            assert isinstance(prepared_data, dict)
            return self._finish_model_commit(
                run_id, manifest, source, prepared_data, first, second, stop
            )
        prepared = prepare_summary(source.artifact, run_id, str(manifest["created_at"]), parsed)
        prepared_data = artifact_data(prepared)
        if not self._has(run_id, "step.output_staged", first_id):
            self._runs.write_evidence(
                run_id,
                prepared_name,
                {
                    "schema_version": 1,
                    "run_id": run_id,
                    "step_id": first_id,
                    "step_name": first["name"],
                    "kind": "prepared_artifact",
                    "data": prepared_data,
                },
            )
            evidence = self._runs.read_evidence(run_id, prepared_name)
            self._event(
                run_id,
                "step.output_staged",
                first_id,
                {
                    "evidence_path": f"evidence/{prepared_name}",
                    "content_hash": evidence["content_hash"],
                },
            )
        if not self._has(run_id, "step.verification_completed", first_id):
            self._event(
                run_id,
                "step.verification_started",
                first_id,
                {"verifier": "verify_model_summary", "version": "1.0.0"},
            )
            self._runs.write_evidence(
                run_id,
                "step-01-verification.json",
                {
                    "schema_version": 1,
                    "run_id": run_id,
                    "step_id": first_id,
                    "step_name": first["name"],
                    "kind": "verification_result",
                    "data": {"valid": True, "call_id": call_id},
                },
            )
            verified = self._runs.read_evidence(run_id, "step-01-verification.json")
            self._event(
                run_id,
                "step.verification_completed",
                first_id,
                {
                    "passed": True,
                    "evidence_path": "evidence/step-01-verification.json",
                    "content_hash": verified["content_hash"],
                },
            )
        if not self._has(run_id, "step.committed", first_id):
            evidence = self._runs.read_evidence(run_id, prepared_name)
            self._event(
                run_id,
                "step.committed",
                first_id,
                {
                    "output_refs": [
                        {
                            "kind": "evidence",
                            "id": "step-01-prepared-artifact",
                            "content_hash": evidence["content_hash"],
                        }
                    ]
                },
            )
            self._faults.checkpoint("after_model_step_committed")
        return self._finish_model_commit(
            run_id, manifest, source, prepared_data, first, second, stop
        )

    def _finish_model_commit(
        self,
        run_id: str,
        manifest: dict[str, object],
        source: StoredArtifact,
        data: dict[str, object],
        first: dict[str, object],
        second: dict[str, object],
        stop: str | None,
    ) -> dict[str, object]:
        if stop == "mock-summarize-concept":
            return self.inspect(run_id) | {"stopped_after_step": stop}
        first_id, second_id = str(first["step_id"]), str(second["step_id"])
        evidence = self._runs.read_evidence(run_id, "step-01-prepared-artifact.json")
        response = self._runs.read_evidence(
            run_id,
            f"model-calls/call_{hashlib.sha256(f'{run_id}:{first_id}:1'.encode()).hexdigest()[:32]}/response-audit.json",
        )
        response_data = response["data"]
        assert isinstance(response_data, dict) and isinstance(response_data["parsed_output"], dict)
        prepared = prepare_summary(
            source.artifact, run_id, str(manifest["created_at"]), response_data["parsed_output"]
        )
        if artifact_data(prepared) != data:
            raise RunConflictError("Prepared model artifact is not deterministic.")
        if not self._has(run_id, "step.created", second_id):
            self._event(
                run_id,
                "step.created",
                second_id,
                {
                    "ordinal": 2,
                    "name": second["name"],
                    "version": second["version"],
                    "side_effect": second["side_effect"],
                },
            )
        if not self._has(run_id, "step.inputs_resolved", second_id):
            self._event(
                run_id,
                "step.inputs_resolved",
                second_id,
                {
                    "input_refs": [
                        {
                            "kind": "step_output",
                            "id": "step-01-prepared-artifact",
                            "content_hash": evidence["content_hash"],
                        }
                    ]
                },
            )
        for event_type in ("step.prepared", "step.execution_started"):
            if not self._has(run_id, event_type, second_id):
                self._event(run_id, event_type, second_id, {"attempt": 1})
        if not self._has(run_id, "step.output_staged", second_id):
            self._runs.write_evidence(
                run_id,
                "step-02-staged-artifact.json",
                {
                    "schema_version": 1,
                    "run_id": run_id,
                    "step_id": second_id,
                    "step_name": second["name"],
                    "kind": "staged_artifact",
                    "data": data,
                },
            )
            staged = self._runs.read_evidence(run_id, "step-02-staged-artifact.json")
            self._event(
                run_id,
                "step.output_staged",
                second_id,
                {
                    "evidence_path": "evidence/step-02-staged-artifact.json",
                    "content_hash": staged["content_hash"],
                },
            )
        if not self._has(run_id, "step.commit_started", second_id):
            self._event(run_id, "step.commit_started", second_id, {"output_id": prepared.id})
        path = f"artifacts/knowledge/{prepared.id}.md"
        if not self._has(run_id, "artifact.canonical_committed", second_id):
            try:
                stored = self._artifacts.save(prepared)
            except DuplicateArtifactId:
                stored = self._artifacts.verify(path)
            self._event(
                run_id,
                "artifact.canonical_committed",
                second_id,
                {
                    "artifact_id": stored.artifact.id,
                    "canonical_path": stored.canonical_path,
                    "content_hash": stored.artifact.content_hash,
                },
            )
        else:
            stored = self._artifacts.verify(path)
        if not self._has(run_id, "artifact.projected", second_id):
            try:
                self._index.upsert(stored)
            except DuplicateArtifactId:
                projected = self._index.get(stored.artifact.id)
                if projected.artifact.content_hash != stored.artifact.content_hash:
                    raise IndexDivergenceError("Existing artifact projection conflicts.")
            self._event(
                run_id,
                "artifact.projected",
                second_id,
                {"artifact_id": stored.artifact.id, "content_hash": stored.artifact.content_hash},
            )
        if not self._has(run_id, "step.verification_completed", second_id):
            self._event(
                run_id,
                "step.verification_started",
                second_id,
                {"verifier": "verify_committed_artifact", "version": "1.0.0"},
            )
            self._runs.write_evidence(
                run_id,
                "step-02-verification.json",
                {
                    "schema_version": 1,
                    "run_id": run_id,
                    "step_id": second_id,
                    "step_name": second["name"],
                    "kind": "verification_result",
                    "data": {"valid": True, "artifact_id": stored.artifact.id},
                },
            )
            verified = self._runs.read_evidence(run_id, "step-02-verification.json")
            self._event(
                run_id,
                "step.verification_completed",
                second_id,
                {
                    "passed": True,
                    "evidence_path": "evidence/step-02-verification.json",
                    "content_hash": verified["content_hash"],
                },
            )
        if not self._has(run_id, "step.committed", second_id):
            self._event(
                run_id,
                "step.committed",
                second_id,
                {
                    "output_refs": [
                        {
                            "kind": "artifact",
                            "id": stored.artifact.id,
                            "content_hash": stored.artifact.content_hash,
                        }
                    ]
                },
            )
        if not self._has(run_id, "run.verification_started", None):
            self._event(run_id, "run.verification_started", None, {"committed_steps": 2})
        outputs = {
            "schema_version": 1,
            "run_id": run_id,
            "status": "SUCCEEDED",
            "completed_at": _now(),
            "artifacts": [
                {
                    "id": stored.artifact.id,
                    "type": stored.artifact.type,
                    "canonical_path": stored.canonical_path,
                    "content_hash": stored.artifact.content_hash,
                }
            ],
            "partial_artifacts": [],
        }
        if self._runs.read_outputs(run_id) is None:
            self._runs.write_outputs(run_id, outputs)
        if not self._has(run_id, "run.succeeded", None):
            self._event(
                run_id, "run.succeeded", None, {"outputs_path": "outputs.json", "artifact_count": 1}
            )
        return self.inspect(run_id)

    def _has(self, run_id: str, event_type: str, step_id: str | None) -> bool:
        return any(
            event.type == event_type and event.step_id == step_id
            for event in self._runs.events(run_id)
        )

    def _lookup(self, artifact_id: str) -> StoredArtifact:
        try:
            projected = self._index.get(artifact_id)
            return self._artifacts.verify(projected.canonical_path)
        except ArtifactNotFound:
            raise

    def _frozen_input(self, run_id: str, manifest: dict[str, object]) -> StoredArtifact:
        inputs = self._runs.read_inputs(run_id)
        if sha256(inputs) != manifest["input_manifest_hash"]:
            raise InputRevisionMismatch("Frozen input manifest hash changed.")
        artifacts = inputs.get("artifacts")
        if (
            not isinstance(artifacts, list)
            or len(artifacts) != 1
            or not isinstance(artifacts[0], dict)
        ):
            raise InputRevisionMismatch("Frozen input manifest is invalid.")
        frozen = artifacts[0]
        stored = self._artifacts.verify(str(frozen["canonical_path"]))
        if (
            stored.artifact.id != frozen["id"]
            or stored.artifact.content_hash != frozen["content_hash"]
        ):
            raise InputRevisionMismatch("Canonical input revision differs from frozen manifest.")
        return stored

    def _validate(self, run_id: str) -> None:
        manifest = self._runs.read_manifest(run_id)
        workflow = manifest.get("workflow")
        steps = manifest.get("steps")
        if not isinstance(workflow, dict) or get(str(workflow.get("name"))).version != workflow.get(
            "version"
        ):
            raise RunConflictError("Run workflow version is unavailable or inconsistent.")
        if not isinstance(steps, list) or len(steps) != 2:
            raise RunConflictError("Run manifest steps are invalid.")
        for ordinal, step in enumerate(steps, 1):
            if not isinstance(step, dict):
                raise RunConflictError("Run manifest step is invalid.")
            expected = deterministic_step_id(
                run_id, ordinal, str(step.get("name")), str(step.get("version"))
            )
            if step.get("ordinal") != ordinal or step.get("step_id") != expected:
                raise RunConflictError("Run manifest deterministic step ID is invalid.")
        self._frozen_input(run_id, manifest)
        if workflow.get("name") == "sample.mock-summarize-concept":
            if self._modeling is None:
                raise RunConflictError("Model workflow is not configured.")
            frozen = manifest.get("protocol_hashes")
            if not isinstance(frozen, list) or len(frozen) != 1 or not isinstance(frozen[0], dict):
                raise RunConflictError("Frozen protocol reference is invalid.")
            source = self._frozen_input(run_id, manifest)
            self._modeling.verify_frozen(frozen[0], source.artifact.sensitivity)
        events = self._runs.events(run_id)
        verify_events(events, tuple(str(step["step_id"]) for step in steps))
        canonical_by_step: dict[str, StoredArtifact] = {}
        for event in events:
            evidence_path = event.payload.get("evidence_path")
            if isinstance(evidence_path, str):
                self._runs.read_evidence(run_id, evidence_path.removeprefix("evidence/"))
            if event.type == "artifact.canonical_committed" and event.step_id is not None:
                stored = self._artifacts.verify(str(event.payload.get("canonical_path")))
                if stored.artifact.content_hash != event.payload.get("content_hash"):
                    raise RunConflictError(
                        "Canonical commit event conflicts with canonical artifact."
                    )
                canonical_by_step[event.step_id] = stored
            if event.type == "artifact.projected" and event.step_id is not None:
                canonical = canonical_by_step.get(event.step_id)
                if canonical is None:
                    raise RunConflictError("Projection event has no canonical commit.")
                projected = self._index.get(canonical.artifact.id)
                if (
                    projected.canonical_path != canonical.canonical_path
                    or projected.artifact.content_hash != canonical.artifact.content_hash
                    or projected.artifact.workspace_id != canonical.artifact.workspace_id
                ):
                    raise IndexDivergenceError("Projection event conflicts with derived index.")
        state = self._state(run_id)
        outputs = self._runs.read_outputs(run_id)
        if state in {RunState.SUCCEEDED, RunState.CANCELLED}:
            if (
                outputs is None
                or outputs.get("run_id") != run_id
                or outputs.get("status") != state.value
            ):
                raise RunConflictError("Terminal outputs manifest is missing or inconsistent.")

    @staticmethod
    def _artifact_id_from_path(path: str) -> str:
        return path.rsplit("/", 1)[-1].removesuffix(".md")

    def _state(self, run_id: str) -> RunState:
        types = [e.type for e in self._runs.events(run_id)]
        if "run.succeeded" in types:
            return RunState.SUCCEEDED
        if "run.cancelled" in types:
            return RunState.CANCELLED
        if "run.failed" in types:
            return RunState.FAILED
        return RunState.RUNNING

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
        event = Event(
            **{**bare.__dict__, "event_hash": sha256(event_mapping(bare, include_hash=False))}
        )
        self._runs.append(run_id, event)

    def _view(self, manifest: dict[str, object], events: list[Event]) -> dict[str, object]:
        committed = sum(1 for e in events if e.type == "step.committed")
        outputs = self._runs.read_outputs(str(manifest["run_id"]))
        produced = [] if outputs is None else outputs.get("artifacts", [])
        workflow = manifest["workflow"]
        assert isinstance(workflow, dict)
        name = workflow["name"]
        assert isinstance(name, str)
        result: dict[str, object] = {
            "run_id": manifest["run_id"],
            "workflow": name,
            "state": self._state(str(manifest["run_id"])).value,
            "committed_steps": committed,
            "next_step": None
            if committed == 2
            else "commit-model-summary"
            if committed and name == "sample.mock-summarize-concept"
            else "commit-derived-concept"
            if committed
            else "mock-summarize-concept"
            if name == "sample.mock-summarize-concept"
            else "prepare-derived-concept",
            "produced_artifacts": produced,
        }
        if name == "sample.mock-summarize-concept":
            calls = []
            for event in events:
                if event.type == "model.response_validated":
                    path = str(event.payload["evidence_path"]).removeprefix("evidence/")
                    envelope = self._runs.read_evidence(str(manifest["run_id"]), path)
                    data = envelope["data"]
                    assert isinstance(data, dict) and isinstance(data.get("usage"), dict)
                    budget_path = path.rsplit("/", 1)[0] + "/budget-audit.json"
                    budget = self._runs.read_evidence(str(manifest["run_id"]), budget_path)["data"]
                    assert isinstance(budget, dict)
                    calls.append(
                        {
                            "call_id": event.payload["call_id"],
                            "provider": data["provider"],
                            "model": data["model"],
                            "model_revision": data["model_revision"],
                            "cache_hit": data["cache_hit"],
                            "origin_run_id": data["origin_run_id"],
                            "origin_call_id": data["origin_call_id"],
                            "provider_calls": budget["provider_calls"],
                            "input_tokens": data["usage"]["input_tokens"],
                            "output_tokens": data["usage"]["output_tokens"],
                            "token_measurement": data["usage"]["token_measurement"],
                            "response_hash": data["response_hash"],
                        }
                    )
            result["model_calls"] = calls
        return result

    def _frontier(self, run_id: str) -> str:
        events = self._runs.events(run_id)
        return events[-1].type if events else "created"
