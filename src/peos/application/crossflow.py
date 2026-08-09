"""Deterministic cross-workflow bridge and independent verification."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from peos.domain.artifacts.model import Artifact, Author, Provenance, StoredArtifact
from peos.domain.crossflow.model import parse_request
from peos.domain.errors import (
    CrossflowConflict,
    CrossflowInputInvalid,
    DuplicateArtifactId,
    RunConflictError,
    TerminalRunError,
)
from peos.domain.relations.model import materialize_links
from peos.domain.runs.events import event_mapping, verify_events
from peos.domain.runs.model import Event, deterministic_step_id, sha256
from peos.ports.artifact_index import ArtifactIndex
from peos.ports.artifact_repository import ArtifactRepository
from peos.ports.fault_injector import FaultInjector, NoOpFaultInjector
from peos.ports.relation_index import RelationIndex
from peos.ports.run_repository import RunRepository
from peos.workflows.crossflow import WORKFLOW

JsonObject = dict[str, Any]


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _raw_hash(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class CrossflowService:
    def __init__(
        self,
        workspace_id: str,
        runs: RunRepository,
        artifacts: ArtifactRepository,
        index: ArtifactIndex,
        relations: RelationIndex,
        fault_injector: FaultInjector | None = None,
    ) -> None:
        self._workspace_id = workspace_id
        self._runs = runs
        self._artifacts = artifacts
        self._index = index
        self._relations = relations
        self._faults = fault_injector or NoOpFaultInjector()

    def start(self, request_path: Path, stop_after_step: str | None = None) -> JsonObject:
        raw = self._read_request(request_path)
        request = parse_request(json.loads(raw.decode("utf-8")))
        self._derive(request, "run_" + "0" * 32, "1970-01-01T00:00:00Z", validate_only=True)
        run_id = "run_" + uuid.uuid4().hex
        inputs: JsonObject = {
            "schema_version": 1,
            "request_bytes_hex": raw.hex(),
            "request_hash": _raw_hash(raw),
        }
        self._create_run(run_id, inputs)
        return self._execute(run_id, stop_after_step)

    def resume(self, run_id: str) -> JsonObject:
        if self._terminal(run_id):
            raise RunConflictError("Terminal run cannot resume.")
        self._event(run_id, "run.resumed", None, {"next_step": self.inspect(run_id)["next_step"]})
        return self._execute(run_id, None)

    def _execute(self, run_id: str, stop: str | None) -> JsonObject:
        steps = self._steps(run_id)
        if not self._committed(run_id, str(steps[0]["step_id"])):
            self._resolve(run_id, steps[0])
            self._faults.checkpoint("after_crossflow_inputs_resolved")
        if stop == "resolve-crossflow-inputs":
            return self.inspect(run_id) | {"stopped_after_step": stop}
        if not self._committed(run_id, str(steps[1]["step_id"])):
            self._commit(run_id, steps[1])
        self._finalize(run_id)
        return self.inspect(run_id)

    def _resolve(self, run_id: str, step: JsonObject) -> None:
        step_id = str(step["step_id"])
        self._ensure_step_started(run_id, step)
        inputs = self._checked_inputs(run_id)
        raw = bytes.fromhex(str(inputs["request_bytes_hex"]))
        if _raw_hash(raw) != inputs["request_hash"]:
            raise CrossflowConflict("Frozen crossflow request hash is invalid.")
        request = parse_request(json.loads(raw.decode("utf-8")))
        created = str(self._runs.read_manifest(run_id)["created_at"])
        preparation = self._derive(request, run_id, created)
        evidence = self._write_evidence(
            run_id,
            step_id,
            "crossflow/preparation.json",
            "crossflow_preparation",
            preparation,
        )
        self._finish_step(run_id, step_id, "crossflow/preparation.json", evidence, [])

    def _derive(
        self, request: JsonObject, run_id: str, created: str, *, validate_only: bool = False
    ) -> JsonObject:
        kind = str(request["kind"])
        if kind == "project_failure_to_learning_exercise":
            packet = self._exact(
                str(request["project_packet_id"]),
                str(request["project_packet_revision"]),
                "project.codex_packet",
            )
            failure, target = request["failure"], request["learning_target"]
            verification = cast(JsonObject, packet.artifact.payload)["verification"]
            if not isinstance(verification, dict) or (
                failure["verification_cwd"] != verification["cwd"]
                or failure["verification_argv"] != verification["argv"]
                or failure["expected_exit_code"] != verification["expected_exit_code"]
                or failure["reported_exit_code"] == failure["expected_exit_code"]
            ):
                raise CrossflowInputInvalid("Reported failure does not match the packet contract.")
            failure_hash = sha256(failure)
            payload: JsonObject = {
                "schema_version": 1,
                "concept_id": target["concept_id"],
                "concept_title": target["concept_title"],
                "dimension": "application",
                "prompt": (
                    f'A project verification reported failure at "{failure["failed_check"]}".\n\n'
                    f"Expected:\n{failure['expected_behavior']}\n\n"
                    f"Observed:\n{failure['observed_behavior']}\n\nIdentify the failing check."
                ),
                "estimated_minutes": target["estimated_minutes"],
                "answer": {"kind": "exact_text", "accepted": [failure["failed_check"]]},
                "origin": {
                    "kind": "project_failure",
                    "project_packet_id": packet.artifact.id,
                    "project_packet_revision": packet.artifact.content_hash,
                    "failure_evidence_hash": failure_hash,
                    "verification_provenance": "reported",
                    "failed_check": failure["failed_check"],
                    "expected_behavior": failure["expected_behavior"],
                    "observed_behavior": failure["observed_behavior"],
                    "reported_by": failure["reported_by"],
                },
            }
            proposal = self._proposal(
                run_id,
                created,
                kind,
                "learning.exercise",
                f"Project failure exercise: {target['concept_title']}",
                payload,
                ({"rel": "derived_from", "target": packet.artifact.id},),
                (packet,),
                f"# Project Failure Exercise\n\n{payload['prompt']}\n",
            )
        elif kind == "research_claim_to_project_adr":
            claim = self._exact(
                str(request["research_claim_id"]),
                str(request["research_claim_revision"]),
                "research.claim",
            )
            charter = self._exact(
                str(request["project_charter_id"]),
                str(request["project_charter_revision"]),
                "project.charter",
            )
            self._verify_source_refs(claim)
            claim_payload = cast(JsonObject, claim.artifact.payload)
            if claim_payload["evidence_status"] != "SUPPORTED":
                raise CrossflowInputInvalid("Only a SUPPORTED research claim may support an ADR.")
            adr = request["adr"]
            claim_ref = {"artifact_id": claim.artifact.id, "revision": claim.artifact.content_hash}
            charter_ref = {
                "artifact_id": charter.artifact.id,
                "revision": charter.artifact.content_hash,
            }
            payload = {
                "schema_version": 1,
                **adr,
                "project_charter_ref": charter_ref,
                "supporting_claim_refs": [claim_ref],
            }
            body = (
                f"# Context\n\n{adr['context']}\n\n# Decision\n\n{adr['decision']}\n\n"
                f"# Supporting Research\n\n- {claim.artifact.id}@{claim.artifact.content_hash}\n\n"
                f"# Alternatives\n\n"
                + "\n".join(f"- {item}" for item in adr["alternatives"])
                + "\n\n# Consequences\n\n"
                + "\n".join(f"- {item}" for item in adr["consequences"])
                + f"\n\n# What would change this decision\n\n{adr['falsifier']}\n"
            )
            proposal = self._proposal(
                run_id,
                created,
                kind,
                "project.adr",
                f"ADR: {adr['decision_key']}",
                payload,
                (
                    {"source": claim.artifact.id, "rel": "supports"},
                    {"rel": "references", "target": charter.artifact.id},
                ),
                (claim, charter),
                body,
            )
        else:
            goal = self._exact(
                str(request["learning_goal_id"]),
                str(request["learning_goal_revision"]),
                "learning.goal",
            )
            goal_payload = cast(JsonObject, goal.artifact.payload)
            gap_id = str(request["gap_concept_id"])
            gap = next(
                (item for item in goal_payload["gaps"] if item["concept_id"] == gap_id), None
            )
            if gap is None or gap["reason"] not in {"diagnostic_failure", "not_assessed"}:
                raise CrossflowInputInvalid("Requested concept is not an unresolved canonical gap.")
            concept = next(
                item for item in goal_payload["concept_graph"]["concepts"] if item["id"] == gap_id
            )
            performance = goal_payload["goal"]["performance"]
            question = (
                f"What evidence or explanation would resolve the prerequisite gap "
                f'"{concept["title"]}" for the capability "{performance}"?'
            )
            payload = {
                "question": question,
                "scope": {
                    "included": [
                        f"learning gap {gap_id} from {goal.artifact.id}"
                        f"@{goal.artifact.content_hash}"
                    ],
                    "excluded": [
                        "automatic mastery promotion",
                        "unrelated project changes",
                        "unverified semantic inference",
                    ],
                },
                "success_criterion": (
                    "Produce evidence that resolves, narrows, or falsifies the identified "
                    "prerequisite gap without silently changing learning mastery."
                ),
                "assumptions": ["the gap remains relevant to the frozen learning.goal revision"],
            }
            proposal = self._proposal(
                run_id,
                created,
                kind,
                "research.question",
                f"Research question for learning gap: {concept['title']}",
                payload,
                ({"rel": "derived_from", "target": goal.artifact.id},),
                (goal,),
                f"# Research Question\n\n{question}\n\nGap: {gap_id} ({gap['reason']})\n",
            )
        if validate_only:
            return {"operation": kind, "validated": True}
        return proposal

    def _proposal(
        self,
        run_id: str,
        created: str,
        operation: str,
        type_: str,
        title: str,
        payload: JsonObject,
        links: tuple[object, ...],
        sources: tuple[StoredArtifact, ...],
        body: str,
    ) -> JsonObject:
        identifier = (
            "art_"
            + hashlib.sha256(f"{run_id}:crossflow.bridge:1.0.0:{operation}".encode()).hexdigest()[
                :32
            ]
        )
        source_refs = [
            {"artifact_id": item.artifact.id, "content_hash": item.artifact.content_hash}
            for item in sources
        ]
        artifact = Artifact(
            identifier,
            type_,
            1,
            title,
            "draft",
            self._workspace_id,
            created,
            created,
            (Author("system", "peos"),),
            sources[0].artifact.sensitivity,
            (),
            links,
            Provenance("system", run_id, tuple(source_refs)),
            None,
            body,
            payload,
        )
        edges = materialize_links(identifier, links)
        return {
            "operation": operation,
            "source_refs": source_refs,
            "target": {
                "id": identifier,
                "type": type_,
                "title": title,
                "created_at": created,
                "sensitivity": artifact.sensitivity,
                "body": body,
                "payload": payload,
                "links": list(links),
                "source_refs": source_refs,
            },
            "edges": [
                {
                    "source_artifact_id": edge.source_artifact_id,
                    "relation": edge.relation,
                    "target_artifact_id": edge.target_artifact_id,
                    "host_artifact_id": edge.host_artifact_id,
                }
                for edge in edges
            ],
        }

    def _commit(self, run_id: str, step: JsonObject) -> None:
        step_id = str(step["step_id"])
        self._ensure_step_started(run_id, step)
        request = self._frozen_request(run_id)
        created = str(self._runs.read_manifest(run_id)["created_at"])
        expected = self._derive(request, run_id, created)
        preparation = self._data(run_id, "crossflow/preparation.json")
        if sha256(expected) != sha256(preparation):
            raise CrossflowConflict("Crossflow preparation does not rederive exactly.")
        target = cast(JsonObject, preparation["target"])
        artifact = Artifact(
            str(target["id"]),
            str(target["type"]),
            1,
            str(target["title"]),
            "draft",
            self._workspace_id,
            str(target["created_at"]),
            str(target["created_at"]),
            (Author("system", "peos"),),
            str(target["sensitivity"]),
            (),
            tuple(target["links"]),
            Provenance("system", run_id, tuple(target["source_refs"])),
            None,
            str(target["body"]),
            cast(JsonObject, target["payload"]),
        )
        stored = self._save_target(run_id, step_id, artifact)
        ref: dict[str, object] = {
            "artifact_id": stored.artifact.id,
            "content_hash": stored.artifact.content_hash,
        }
        evidence = self._write_evidence(
            run_id,
            step_id,
            "crossflow/verification.json",
            "crossflow_verification",
            {"output": ref, "operation": preparation["operation"], "edges": preparation["edges"]},
        )
        self._finish_step(run_id, step_id, "crossflow/verification.json", evidence, [ref])

    def _save_target(self, run_id: str, step_id: str, artifact: Artifact) -> StoredArtifact:
        path = f"artifacts/knowledge/{artifact.id}.md"
        try:
            stored = self._artifacts.save(artifact)
        except DuplicateArtifactId:
            stored = self._artifacts.verify(path)
            if Artifact(**{**stored.artifact.__dict__, "content_hash": None}) != artifact:
                raise CrossflowConflict("Existing deterministic crossflow target conflicts.")
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
        self._faults.checkpoint("after_crossflow_target_canonical_committed")
        try:
            self._index.upsert(stored)
        except DuplicateArtifactId:
            projected = self._index.get(stored.artifact.id)
            if projected.artifact.content_hash != stored.artifact.content_hash:
                raise CrossflowConflict("Crossflow artifact projection conflicts.")
        except Exception as error:
            self._artifacts.write_index_dirty(stored)
            raise CrossflowConflict("Crossflow relation projection failed.") from error
        self._verify_projected_edges(stored)
        self._event(
            run_id,
            "artifact.projected",
            step_id,
            {"artifact_id": stored.artifact.id, "content_hash": stored.artifact.content_hash},
        )
        return stored

    def verify(self, run_id: str) -> JsonObject:
        steps = self._steps(run_id)
        verify_events(self._runs.events(run_id), tuple(str(item["step_id"]) for item in steps))
        request = self._frozen_request(run_id)
        created = str(self._runs.read_manifest(run_id)["created_at"])
        expected = self._derive(request, run_id, created)
        preparation = self._data(run_id, "crossflow/preparation.json")
        if sha256(expected) != sha256(preparation):
            raise CrossflowConflict("Crossflow preparation verification failed.")
        committed = sum(item.type == "step.committed" for item in self._runs.events(run_id))
        if committed == 2:
            output = self._data(run_id, "crossflow/verification.json")["output"]
            stored = self._exact(
                str(output["artifact_id"]),
                str(output["content_hash"]),
                str(preparation["target"]["type"]),
            )
            self._verify_projected_edges(stored)
            outputs = self._runs.read_outputs(run_id)
            if outputs != {"schema_version": 1, "artifacts": [output]}:
                raise CrossflowConflict("Crossflow outputs conflict with verification evidence.")
        return {"run_id": run_id, "workflow": WORKFLOW.name, "valid": True, "read_only": True}

    def inspect(self, run_id: str) -> JsonObject:
        events = self._runs.events(run_id)
        committed = sum(item.type == "step.committed" for item in events)
        steps = self._steps(run_id)
        result: JsonObject = {
            "run_id": run_id,
            "workflow": WORKFLOW.name,
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
            prep = self._data(run_id, "crossflow/preparation.json")
            result.update(
                {
                    "operation": prep["operation"],
                    "output_artifact_id": prep["target"]["id"],
                    "output_artifact_type": prep["target"]["type"],
                    "relation_count": len(prep["edges"]),
                }
            )
        except Exception:
            pass
        return result

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

    def _finalize(self, run_id: str) -> None:
        if self._terminal(run_id):
            return
        output = self._data(run_id, "crossflow/verification.json")["output"]
        self._runs.write_outputs(run_id, {"schema_version": 1, "artifacts": [output]})
        self._event(run_id, "run.verification_started", None, {"committed_steps": 2})
        self.verify(run_id)
        self._event(
            run_id, "run.succeeded", None, {"outputs_path": "outputs.json", "artifact_count": 1}
        )

    def _verify_projected_edges(self, stored: StoredArtifact) -> None:
        expected = {
            edge.logical_key
            for edge in materialize_links(
                stored.artifact.id, stored.artifact.links, stored.artifact.content_hash
            )
        }
        actual = {
            edge.logical_key
            for edge in self._relations.outgoing(stored.artifact.id)
            + self._relations.incoming(stored.artifact.id)
            if edge.host_artifact_id == stored.artifact.id
        }
        if expected != actual:
            raise CrossflowConflict("Crossflow relation projection differs from canonical links.")

    def _exact(self, identifier: str, revision: str, type_: str) -> StoredArtifact:
        projected = self._index.get(identifier)
        stored = self._artifacts.verify(projected.canonical_path)
        if (
            stored.artifact.type != type_
            or stored.artifact.content_hash != revision
            or projected.artifact.content_hash != revision
        ):
            raise CrossflowInputInvalid("Crossflow source type or exact revision is invalid.")
        return stored

    def _verify_source_refs(self, artifact: StoredArtifact) -> None:
        for ref in artifact.artifact.provenance.source_refs:
            if not isinstance(ref, dict):
                raise CrossflowInputInvalid("Research claim source reference is invalid.")
            self._exact(str(ref["artifact_id"]), str(ref["content_hash"]), "research.source")

    def _frozen_request(self, run_id: str) -> JsonObject:
        inputs = self._checked_inputs(run_id)
        raw = bytes.fromhex(str(inputs["request_bytes_hex"]))
        if _raw_hash(raw) != inputs["request_hash"]:
            raise CrossflowConflict("Frozen crossflow request hash is invalid.")
        return parse_request(json.loads(raw.decode("utf-8")))

    def _create_run(self, run_id: str, inputs: JsonObject) -> None:
        steps = [
            {
                "ordinal": item.ordinal,
                "name": item.name,
                "version": item.version,
                "side_effect": item.side_effect,
                "step_id": deterministic_step_id(run_id, item.ordinal, item.name, item.version),
            }
            for item in WORKFLOW.steps
        ]
        manifest: JsonObject = {
            "schema_version": 1,
            "run_id": run_id,
            "created_at": _now(),
            "workflow": {"name": WORKFLOW.name, "version": WORKFLOW.version},
            "input_manifest_hash": sha256(inputs),
            "steps": steps,
        }
        self._runs.create(manifest, inputs)
        self._event(
            run_id,
            "run.created",
            None,
            {"workflow_name": WORKFLOW.name, "workflow_version": WORKFLOW.version},
        )
        self._event(
            run_id,
            "run.planned",
            None,
            {"step_count": 2, "input_manifest_hash": manifest["input_manifest_hash"]},
        )
        self._event(run_id, "run.started", None, {})

    def _ensure_step_started(self, run_id: str, step: JsonObject) -> None:
        step_id = str(step["step_id"])
        if any(
            item.type == "step.created" and item.step_id == step_id
            for item in self._runs.events(run_id)
        ):
            return
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
            {"verifier": "verify_crossflow_step", "version": "1.0.0"},
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
        value = self._runs.read_evidence(run_id, name)["data"]
        if not isinstance(value, dict):
            raise CrossflowConflict("Crossflow evidence is invalid.")
        return cast(JsonObject, value)

    def _checked_inputs(self, run_id: str) -> JsonObject:
        inputs = self._runs.read_inputs(run_id)
        if sha256(inputs) != self._runs.read_manifest(run_id)["input_manifest_hash"]:
            raise CrossflowConflict("Crossflow input manifest hash changed.")
        return cast(JsonObject, inputs)

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
    def _read_request(path: Path) -> bytes:
        try:
            raw = path.read_bytes()
            json.loads(raw.decode("utf-8"))
            return raw
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CrossflowInputInvalid("Crossflow request is not strict UTF-8 JSON.") from error
