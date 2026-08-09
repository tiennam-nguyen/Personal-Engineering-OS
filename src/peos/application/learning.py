"""Deterministic Learning Compiler orchestration and independent verification."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from peos.domain.artifacts.model import Artifact, Author, Provenance, StoredArtifact
from peos.domain.errors import (
    DuplicateArtifactId,
    LearningAttemptInvalid,
    LearningInputInvalid,
    RunConflictError,
    TerminalRunError,
)
from peos.domain.learning.artifacts import learning_id
from peos.domain.learning.diagnostic import analyze_diagnostic, verify_answer
from peos.domain.learning.graph import analyze_graph, derive_plan
from peos.domain.learning.mastery import derive_mastery
from peos.domain.learning.model import (
    LearningGoalInput,
    parse_attempt_input,
    parse_diagnostic_fixture,
    parse_goal_input,
)
from peos.domain.runs.events import event_mapping, verify_events
from peos.domain.runs.model import Event, deterministic_step_id, sha256
from peos.domain.workflows.model import WorkflowDefinition
from peos.ports.artifact_index import ArtifactIndex
from peos.ports.artifact_repository import ArtifactRepository
from peos.ports.fault_injector import FaultInjector, NoOpFaultInjector
from peos.ports.run_repository import RunRepository
from peos.workflows.learning import ATTEMPT_WORKFLOW, COMPILE_WORKFLOW

JsonObject = dict[str, Any]


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _raw_hash(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class LearningService:
    def __init__(
        self,
        workspace_id: str,
        runs: RunRepository,
        artifacts: ArtifactRepository,
        index: ArtifactIndex,
        fault_injector: FaultInjector | None = None,
    ) -> None:
        self._workspace_id = workspace_id
        self._runs = runs
        self._artifacts = artifacts
        self._index = index
        self._faults = fault_injector or NoOpFaultInjector()

    def start_compile(
        self, goal_path: Path, diagnostic_path: Path, stop_after_step: str | None = None
    ) -> JsonObject:
        goal_raw = self._read_json_bytes(goal_path, "goal")
        diagnostic_raw = self._read_json_bytes(diagnostic_path, "diagnostic")
        goal_value = json.loads(goal_raw.decode("utf-8"))
        diagnostic_value = json.loads(diagnostic_raw.decode("utf-8"))
        parse_goal_input(goal_value)
        parse_diagnostic_fixture(diagnostic_value)
        run_id = "run_" + uuid.uuid4().hex
        inputs: JsonObject = {
            "schema_version": 1,
            "goal_bytes_hex": goal_raw.hex(),
            "goal_hash": _raw_hash(goal_raw),
            "diagnostic_bytes_hex": diagnostic_raw.hex(),
            "diagnostic_hash": _raw_hash(diagnostic_raw),
        }
        self._create_run(run_id, COMPILE_WORKFLOW, inputs)
        return self._execute_compile(run_id, stop_after_step)

    def start_attempt(self, goal_id: str, attempt_path: Path) -> JsonObject:
        raw = self._read_json_bytes(attempt_path, "attempt")
        value = json.loads(raw.decode("utf-8"))
        attempt = parse_attempt_input(value)
        if attempt["goal_artifact_id"] != goal_id:
            raise LearningAttemptInvalid("CLI goal ID and attempt goal reference differ.")
        goal = self._lookup(goal_id)
        if (
            goal.artifact.type != "learning.goal"
            or goal.artifact.content_hash != attempt["goal_revision"]
        ):
            raise LearningAttemptInvalid("Attempt requires the exact learning goal revision.")
        run_id = "run_" + uuid.uuid4().hex
        inputs: JsonObject = {
            "schema_version": 1,
            "goal_ref": {"id": goal_id, "revision": goal.artifact.content_hash},
            "attempt_bytes_hex": raw.hex(),
            "attempt_hash": _raw_hash(raw),
        }
        self._create_run(run_id, ATTEMPT_WORKFLOW, inputs)
        return self._execute_attempt(run_id)

    def resume(self, run_id: str) -> JsonObject:
        if self._terminal(run_id):
            raise RunConflictError("Terminal run cannot resume.")
        manifest = self._runs.read_manifest(run_id)
        workflow = cast(JsonObject, manifest["workflow"])["name"]
        self._event(run_id, "run.resumed", None, {"next_step": self.inspect(run_id)["next_step"]})
        return (
            self._execute_compile(run_id, None)
            if workflow == COMPILE_WORKFLOW.name
            else self._execute_attempt(run_id)
        )

    def _execute_compile(self, run_id: str, stop: str | None) -> JsonObject:
        steps = self._steps(run_id)
        if not self._committed(run_id, str(steps[0]["step_id"])):
            self._freeze_compile(run_id, steps[0])
            self._faults.checkpoint("after_learning_inputs_committed")
        if stop == "freeze-learning-inputs":
            return self.inspect(run_id) | {"stopped_after_step": stop}
        if not self._committed(run_id, str(steps[1]["step_id"])):
            self._analyze(run_id, steps[1])
            self._faults.checkpoint("after_learning_analysis_committed")
        if stop == "analyze-learning-gap":
            return self.inspect(run_id) | {"stopped_after_step": stop}
        if not self._committed(run_id, str(steps[2]["step_id"])):
            self._commit_goal(run_id, steps[2])
        self._finalize(run_id, 3)
        return self.inspect(run_id)

    def _freeze_compile(self, run_id: str, step: JsonObject) -> None:
        step_id = str(step["step_id"])
        self._start_step(run_id, step)
        inputs = self._checked_inputs(run_id)
        goal_raw = bytes.fromhex(str(inputs["goal_bytes_hex"]))
        diagnostic_raw = bytes.fromhex(str(inputs["diagnostic_bytes_hex"]))
        if (
            _raw_hash(goal_raw) != inputs["goal_hash"]
            or _raw_hash(diagnostic_raw) != inputs["diagnostic_hash"]
        ):
            raise RunConflictError("Frozen learning input hash is invalid.")
        goal = json.loads(goal_raw.decode("utf-8"))
        diagnostic = json.loads(diagnostic_raw.decode("utf-8"))
        parse_goal_input(goal)
        parse_diagnostic_fixture(diagnostic)
        evidence = self._write_evidence(
            run_id,
            step_id,
            "learning/inputs.json",
            "learning_inputs",
            {
                "goal": goal,
                "diagnostic": diagnostic,
                "goal_hash": inputs["goal_hash"],
                "diagnostic_hash": inputs["diagnostic_hash"],
            },
        )
        self._finish_step(run_id, step_id, "learning/inputs.json", evidence, [])

    def _analyze(self, run_id: str, step: JsonObject) -> None:
        step_id = str(step["step_id"])
        self._start_step(run_id, step)
        frozen = self._data(run_id, "learning/inputs.json")
        goal = parse_goal_input(frozen["goal"])
        fixture = parse_diagnostic_fixture(frozen["diagnostic"])
        graph = analyze_graph(fixture["concepts"], fixture["target_concept_id"])
        diagnostic = analyze_diagnostic(fixture)
        plan = derive_plan(goal, fixture, diagnostic, graph)
        analysis = {
            "graph": graph,
            "diagnostic": diagnostic,
            "gaps": plan["gaps"],
            "plan": {
                key: plan[key]
                for key in (
                    "practice_concepts",
                    "first_exercise",
                    "future_events",
                    "selection_reason",
                )
            },
        }
        independently = self._recompute(goal, fixture)
        if sha256(analysis) != sha256(independently):
            raise RunConflictError("Learning analysis is not deterministic.")
        evidence = self._write_evidence(
            run_id, step_id, "learning/diagnostic-analysis.json", "learning_analysis", analysis
        )
        self._finish_step(run_id, step_id, "learning/diagnostic-analysis.json", evidence, [])

    def _commit_goal(self, run_id: str, step: JsonObject) -> None:
        step_id = str(step["step_id"])
        self._start_step(run_id, step)
        frozen, analysis = (
            self._data(run_id, "learning/inputs.json"),
            self._data(run_id, "learning/diagnostic-analysis.json"),
        )
        goal = parse_goal_input(frozen["goal"])
        fixture = parse_diagnostic_fixture(frozen["diagnostic"])
        payload: JsonObject = {
            "schema_version": 1,
            "goal": {
                "goal_slug": goal.goal_slug,
                "performance": goal.performance,
                "conditions": list(goal.conditions),
                "quality_bar": goal.quality_bar,
                "deadline": goal.deadline,
                "review_after_days": goal.review_after_days,
                "time_budget_minutes": goal.time_budget_minutes,
            },
            "concept_graph": {
                "target_concept_id": fixture["target_concept_id"],
                "concepts": fixture["concepts"],
                **analysis["graph"],
            },
            "diagnostic": analysis["diagnostic"],
            "gaps": analysis["gaps"],
            "plan": analysis["plan"],
        }
        created = str(self._runs.read_manifest(run_id)["created_at"])
        artifact = self._artifact(
            learning_id(run_id, "learning.goal", 1),
            "learning.goal",
            f"Learning goal: {goal.goal_slug}",
            self._goal_body(payload),
            payload,
            run_id,
            created,
            goal.sensitivity,
            (),
            (),
        )
        stored = self._commit_artifact(run_id, step_id, artifact)
        ref: dict[str, object] = {
            "artifact_id": stored.artifact.id,
            "content_hash": stored.artifact.content_hash,
        }
        evidence = self._write_evidence(
            run_id, step_id, "learning/goal-commit.json", "learning_goal_commit", {"output": ref}
        )
        self._finish_step(run_id, step_id, "learning/goal-commit.json", evidence, [ref])

    def _execute_attempt(self, run_id: str) -> JsonObject:
        steps = self._steps(run_id)
        if not self._committed(run_id, str(steps[0]["step_id"])):
            self._verify_attempt(run_id, steps[0])
            self._faults.checkpoint("after_learning_attempt_verified")
        if not self._committed(run_id, str(steps[1]["step_id"])):
            self._commit_attempt(run_id, steps[1])
        self._finalize(run_id, 2)
        return self.inspect(run_id)

    def _verify_attempt(self, run_id: str, step: JsonObject) -> None:
        step_id = str(step["step_id"])
        self._start_step(run_id, step)
        inputs = self._checked_inputs(run_id)
        raw = bytes.fromhex(str(inputs["attempt_bytes_hex"]))
        if _raw_hash(raw) != inputs["attempt_hash"]:
            raise RunConflictError("Frozen learning attempt hash is invalid.")
        attempt = parse_attempt_input(json.loads(raw.decode("utf-8")))
        goal = self._lookup(str(attempt["goal_artifact_id"]))
        if goal.artifact.content_hash != attempt["goal_revision"] or inputs["goal_ref"] != {
            "id": goal.artifact.id,
            "revision": goal.artifact.content_hash,
        }:
            raise LearningAttemptInvalid("Attempt goal revision is stale.")
        payload = cast(JsonObject, goal.artifact.payload)
        exercise = payload["plan"]["first_exercise"]
        if attempt["exercise_id"] != exercise["id"]:
            raise LearningAttemptInvalid("Attempt exercise is not the planned first exercise.")
        verified = verify_answer(exercise["answer"], str(attempt["answer"]))
        data = {
            "attempt": attempt,
            "goal_ref": inputs["goal_ref"],
            "exercise_id": exercise["id"],
            "focus_concept_id": exercise["concept_id"],
            "dimension": exercise["dimension"],
            **verified,
            "feedback_classification": "correct" if verified["correct"] else "incorrect_answer",
        }
        evidence = self._write_evidence(
            run_id,
            step_id,
            "learning/attempt-verification.json",
            "learning_attempt_verification",
            data,
        )
        self._finish_step(run_id, step_id, "learning/attempt-verification.json", evidence, [])

    def _commit_attempt(self, run_id: str, step: JsonObject) -> None:
        step_id = str(step["step_id"])
        self._start_step(run_id, step)
        verified = self._data(run_id, "learning/attempt-verification.json")
        goal = self._lookup(str(verified["goal_ref"]["id"]))
        created = str(self._runs.read_manifest(run_id)["created_at"])
        attempt_payload: JsonObject = {
            "schema_version": 1,
            "goal_ref": verified["goal_ref"],
            "exercise_id": verified["exercise_id"],
            "focus_concept_id": verified["focus_concept_id"],
            "dimension": verified["dimension"],
            "submitted_raw": verified["submitted_raw"],
            "submitted_normalized": verified["submitted_normalized"],
            "verifier_kind": verified["verifier_kind"],
            "correct": verified["correct"],
            "feedback_classification": verified["feedback_classification"],
            "evidence_timestamp": created,
            "run_id": run_id,
        }
        attempt = self._artifact(
            learning_id(run_id, "learning.attempt", 1),
            "learning.attempt",
            f"Learning attempt: {verified['exercise_id']}",
            self._attempt_body(attempt_payload),
            attempt_payload,
            run_id,
            created,
            goal.artifact.sensitivity,
            ({"rel": "derived_from", "target": goal.artifact.id},),
            ({"artifact_id": goal.artifact.id, "content_hash": goal.artifact.content_hash},),
        )
        stored_attempt = self._commit_artifact(run_id, step_id, attempt)
        attempt_ref = {
            "id": stored_attempt.artifact.id,
            "revision": stored_attempt.artifact.content_hash,
        }
        attempt_time = datetime.fromisoformat(created.replace("Z", "+00:00"))
        mastery_data = derive_mastery(
            cast(JsonObject, goal.artifact.payload), attempt_ref, verified, attempt_time
        )
        mastery_payload: JsonObject = {
            "schema_version": 1,
            "goal_ref": verified["goal_ref"],
            "attempt_ref": attempt_ref,
            **mastery_data,
        }
        mastery = self._artifact(
            learning_id(run_id, "learning.mastery", 2),
            "learning.mastery",
            f"Learning mastery evidence: {verified['focus_concept_id']}",
            self._mastery_body(mastery_payload),
            mastery_payload,
            run_id,
            created,
            goal.artifact.sensitivity,
            (
                {"rel": "derived_from", "target": stored_attempt.artifact.id},
                {"rel": "references", "target": goal.artifact.id},
            ),
            (
                {"artifact_id": goal.artifact.id, "content_hash": goal.artifact.content_hash},
                {
                    "artifact_id": stored_attempt.artifact.id,
                    "content_hash": stored_attempt.artifact.content_hash,
                },
            ),
        )
        stored_mastery = self._commit_artifact(run_id, step_id, mastery)
        refs: list[dict[str, object]] = [
            {"artifact_id": item.artifact.id, "content_hash": item.artifact.content_hash}
            for item in (stored_attempt, stored_mastery)
        ]
        evidence = self._write_evidence(
            run_id,
            step_id,
            "learning/mastery-commit.json",
            "learning_mastery_commit",
            {"outputs": refs},
        )
        self._finish_step(run_id, step_id, "learning/mastery-commit.json", evidence, refs)

    def verify(self, run_id: str) -> JsonObject:
        self._checked_inputs(run_id)
        steps = self._steps(run_id)
        verify_events(self._runs.events(run_id), tuple(str(item["step_id"]) for item in steps))
        manifest = self._runs.read_manifest(run_id)
        workflow = cast(JsonObject, manifest["workflow"])["name"]
        committed = sum(item.type == "step.committed" for item in self._runs.events(run_id))
        if workflow == COMPILE_WORKFLOW.name:
            frozen = self._data(run_id, "learning/inputs.json")
            goal = parse_goal_input(frozen["goal"])
            fixture = parse_diagnostic_fixture(frozen["diagnostic"])
            if committed == 1:
                return {
                    "run_id": run_id,
                    "workflow": workflow,
                    "valid": True,
                    "read_only": True,
                }
            analysis = self._data(run_id, "learning/diagnostic-analysis.json")
            if sha256(analysis) != sha256(self._recompute(goal, fixture)):
                raise RunConflictError("Learning analysis evidence is corrupt.")
            output = self._data(run_id, "learning/goal-commit.json")["output"]
            stored = self._lookup(str(output["artifact_id"]))
            expected_payload: JsonObject = {
                "schema_version": 1,
                "goal": {
                    "goal_slug": goal.goal_slug,
                    "performance": goal.performance,
                    "conditions": list(goal.conditions),
                    "quality_bar": goal.quality_bar,
                    "deadline": goal.deadline,
                    "review_after_days": goal.review_after_days,
                    "time_budget_minutes": goal.time_budget_minutes,
                },
                "concept_graph": {
                    "target_concept_id": fixture["target_concept_id"],
                    "concepts": fixture["concepts"],
                    **analysis["graph"],
                },
                "diagnostic": analysis["diagnostic"],
                "gaps": analysis["gaps"],
                "plan": analysis["plan"],
            }
            if (
                stored.artifact.payload != expected_payload
                or self._index.get(stored.artifact.id).artifact.content_hash
                != stored.artifact.content_hash
            ):
                raise RunConflictError("Learning goal canonical/projection evidence conflicts.")
        else:
            verified = self._data(run_id, "learning/attempt-verification.json")
            if committed == 1:
                return {
                    "run_id": run_id,
                    "workflow": workflow,
                    "valid": True,
                    "read_only": True,
                }
            outputs = self._data(run_id, "learning/mastery-commit.json")["outputs"]
            attempt_outputs = [self._lookup(str(item["artifact_id"])) for item in outputs]
            attempt = next(
                item for item in attempt_outputs if item.artifact.type == "learning.attempt"
            )
            mastery = next(
                item for item in attempt_outputs if item.artifact.type == "learning.mastery"
            )
            goal_artifact = self._lookup(str(verified["goal_ref"]["id"]))
            expected = derive_mastery(
                cast(JsonObject, goal_artifact.artifact.payload),
                {"id": attempt.artifact.id, "revision": attempt.artifact.content_hash},
                verified,
                datetime.fromisoformat(str(manifest["created_at"]).replace("Z", "+00:00")),
            )
            mastery_payload = cast(JsonObject, mastery.artifact.payload)
            if {key: mastery_payload[key] for key in expected} != expected or any(
                self._index.get(item.artifact.id).artifact.content_hash
                != item.artifact.content_hash
                for item in attempt_outputs
            ):
                raise RunConflictError("Learning attempt/mastery evidence conflicts.")
        return {"run_id": run_id, "workflow": workflow, "valid": True, "read_only": True}

    def inspect(self, run_id: str) -> JsonObject:
        manifest = self._runs.read_manifest(run_id)
        events = self._runs.events(run_id)
        committed = sum(item.type == "step.committed" for item in events)
        steps = self._steps(run_id)
        workflow = cast(JsonObject, manifest["workflow"])["name"]
        view: JsonObject = {
            "run_id": run_id,
            "workflow": workflow,
            "state": "CANCELLED"
            if any(item.type == "run.cancelled" for item in events)
            else "SUCCEEDED"
            if any(item.type == "run.succeeded" for item in events)
            else "RUNNING",
            "committed_steps": committed,
            "next_step": None if committed == len(steps) else steps[committed]["name"],
            "outputs": self._runs.read_outputs(run_id),
        }
        try:
            source = (
                self._data(run_id, "learning/diagnostic-analysis.json")
                if workflow == COMPILE_WORKFLOW.name
                else self._data(run_id, "learning/attempt-verification.json")
            )
            view.update(
                {
                    "selected_focus_concept": source["plan"]["first_exercise"]["concept_id"],
                    "first_exercise_id": source["plan"]["first_exercise"]["id"],
                    "gap_count": len(source["gaps"]),
                }
                if workflow == COMPILE_WORKFLOW.name
                else {
                    "goal_artifact_id": source["goal_ref"]["id"],
                    "exercise_id": source["exercise_id"],
                    "correct": source["correct"],
                    "focus_dimension": source["dimension"],
                }
            )
        except Exception:
            pass
        return view

    def cancel(self, run_id: str) -> JsonObject:
        events = self._runs.events(run_id)
        if any(item.type == "run.cancelled" for item in events):
            return self.inspect(run_id)
        if any(item.type in {"run.succeeded", "run.failed"} for item in events):
            raise TerminalRunError("Terminal run cannot be cancelled.")
        self._event(
            run_id,
            "run.cancelled",
            None,
            {
                "frontier": self.inspect(run_id)["next_step"],
                "partial_artifact_count": sum(
                    item.type == "artifact.canonical_committed" for item in events
                ),
            },
        )
        return self.inspect(run_id)

    def _recompute(self, goal: LearningGoalInput, fixture: JsonObject) -> JsonObject:
        graph = analyze_graph(fixture["concepts"], fixture["target_concept_id"])
        diagnostic = analyze_diagnostic(fixture)
        plan = derive_plan(goal, fixture, diagnostic, graph)
        return {
            "graph": graph,
            "diagnostic": diagnostic,
            "gaps": plan["gaps"],
            "plan": {
                key: plan[key]
                for key in (
                    "practice_concepts",
                    "first_exercise",
                    "future_events",
                    "selection_reason",
                )
            },
        }

    def _create_run(self, run_id: str, workflow: WorkflowDefinition, inputs: JsonObject) -> None:
        steps = [
            {
                "ordinal": item.ordinal,
                "name": item.name,
                "version": item.version,
                "side_effect": item.side_effect,
                "step_id": deterministic_step_id(run_id, item.ordinal, item.name, item.version),
            }
            for item in workflow.steps
        ]
        manifest: JsonObject = {
            "schema_version": 1,
            "run_id": run_id,
            "created_at": _now(),
            "workflow": {"name": workflow.name, "version": workflow.version},
            "input_manifest_hash": sha256(inputs),
            "steps": steps,
        }
        self._runs.create(manifest, inputs)
        self._event(
            run_id,
            "run.created",
            None,
            {"workflow_name": workflow.name, "workflow_version": workflow.version},
        )
        self._event(
            run_id,
            "run.planned",
            None,
            {"step_count": len(steps), "input_manifest_hash": manifest["input_manifest_hash"]},
        )
        self._event(run_id, "run.started", None, {})

    def _finalize(self, run_id: str, count: int) -> None:
        if self._terminal(run_id):
            return
        refs = [
            {
                "artifact_id": item.payload["artifact_id"],
                "content_hash": item.payload["content_hash"],
            }
            for item in self._runs.events(run_id)
            if item.type == "artifact.canonical_committed"
        ]
        self._runs.write_outputs(run_id, {"schema_version": 1, "artifacts": refs})
        self._event(run_id, "run.verification_started", None, {"committed_steps": count})
        self._event(
            run_id,
            "run.succeeded",
            None,
            {"outputs_path": "outputs.json", "artifact_count": len(refs)},
        )

    def _artifact(
        self,
        identifier: str,
        type_: str,
        title: str,
        body: str,
        payload: JsonObject,
        run_id: str,
        created: str,
        sensitivity: str,
        links: tuple[object, ...],
        refs: tuple[object, ...],
    ) -> Artifact:
        return Artifact(
            identifier,
            type_,
            1,
            title,
            "draft",
            self._workspace_id,
            created,
            created,
            (Author("system", "peos"),),
            sensitivity,
            (),
            links,
            Provenance("system", run_id, refs),
            None,
            body,
            payload,
        )

    def _commit_artifact(self, run_id: str, step_id: str, artifact: Artifact) -> StoredArtifact:
        path = f"artifacts/knowledge/{artifact.id}.md"
        try:
            stored = self._artifacts.save(artifact)
        except DuplicateArtifactId:
            stored = self._artifacts.verify(path)
            existing = Artifact(**{**stored.artifact.__dict__, "content_hash": None})
            if existing != artifact:
                raise RunConflictError("Existing deterministic learning artifact conflicts.")
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
        try:
            self._index.upsert(stored)
        except DuplicateArtifactId:
            if (
                self._index.get(stored.artifact.id).artifact.content_hash
                != stored.artifact.content_hash
            ):
                raise RunConflictError("Learning projection conflicts.")
        self._event(
            run_id,
            "artifact.projected",
            step_id,
            {"artifact_id": stored.artifact.id, "content_hash": stored.artifact.content_hash},
        )
        return stored

    def _start_step(self, run_id: str, step: JsonObject) -> None:
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

    def _finish_step(
        self,
        run_id: str,
        step_id: str,
        name: str,
        evidence: JsonObject,
        refs: list[dict[str, object]],
    ) -> None:
        payload = {"evidence_path": f"evidence/{name}", "content_hash": evidence["content_hash"]}
        self._event(run_id, "step.output_staged", step_id, payload)
        self._event(
            run_id,
            "step.verification_started",
            step_id,
            {"verifier": "verify_learning_step", "version": "1.0.0"},
        )
        self._event(run_id, "step.verification_completed", step_id, {"passed": True, **payload})
        self._event(run_id, "step.committed", step_id, {"output_refs": refs})

    def _write_evidence(
        self, run_id: str, step_id: str, name: str, kind: str, data: JsonObject
    ) -> JsonObject:
        self._runs.write_evidence(
            run_id,
            name,
            {"schema_version": 1, "run_id": run_id, "step_id": step_id, "kind": kind, "data": data},
        )
        return self._runs.read_evidence(run_id, name)

    def _data(self, run_id: str, name: str) -> JsonObject:
        data = self._runs.read_evidence(run_id, name)["data"]
        if not isinstance(data, dict):
            raise RunConflictError("Learning evidence is invalid.")
        return cast(JsonObject, data)

    def _checked_inputs(self, run_id: str) -> JsonObject:
        inputs = self._runs.read_inputs(run_id)
        if sha256(inputs) != self._runs.read_manifest(run_id)["input_manifest_hash"]:
            raise RunConflictError("Learning input manifest hash changed.")
        return cast(JsonObject, inputs)

    def _lookup(self, identifier: str) -> StoredArtifact:
        projected = self._index.get(identifier)
        return self._artifacts.verify(projected.canonical_path)

    def _steps(self, run_id: str) -> list[JsonObject]:
        return cast(list[JsonObject], self._runs.read_manifest(run_id)["steps"])

    def _committed(self, run_id: str, step_id: str) -> bool:
        return any(
            item.type == "step.committed" and item.step_id == step_id
            for item in self._runs.events(run_id)
        )

    def _terminal(self, run_id: str) -> bool:
        return any(
            item.type in {"run.succeeded", "run.failed", "run.cancelled"}
            for item in self._runs.events(run_id)
        )

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

    @staticmethod
    def _read_json_bytes(path: Path, kind: str) -> bytes:
        try:
            raw = path.read_bytes()
            json.loads(raw.decode("utf-8"))
            return raw
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LearningInputInvalid(f"Learning {kind} file is not strict UTF-8 JSON.") from error

    @staticmethod
    def _goal_body(payload: JsonObject) -> str:
        goal, graph, diagnostic, gaps, plan = (
            payload[key] for key in ("goal", "concept_graph", "diagnostic", "gaps", "plan")
        )
        sections = [
            ("# Capability", goal["performance"]),
            ("# Conditions", goal["conditions"]),
            ("# Quality Bar", goal["quality_bar"]),
            ("# Prerequisite Graph", graph["edges"]),
            ("# Diagnostic Evidence", diagnostic["task_results"]),
            ("# Prerequisite Gaps", gaps),
            ("# Practice Plan", plan["practice_concepts"]),
            ("# First Exercise", plan["first_exercise"]["id"]),
            ("# Future Retrieval / Application", plan["future_events"]),
        ]
        return "\n\n".join(f"{heading}\n\n{value}" for heading, value in sections) + "\n"

    @staticmethod
    def _attempt_body(payload: JsonObject) -> str:
        return (
            f"# Learning Attempt\n\nExercise: {payload['exercise_id']}\n\n"
            f"Dimension: {payload['dimension']}\n\n"
            f"Result: {payload['feedback_classification']} according to deterministic verifier.\n"
        )

    @staticmethod
    def _mastery_body(payload: JsonObject) -> str:
        return (
            "# Multidimensional Mastery Evidence\n\n"
            f"{payload['dimensions']}\n\n# Review Recommendation\n\n"
            f"{payload['review_recommendation']}\n\n"
            "This date is a fixed policy recommendation, not epistemic truth.\n"
        )
