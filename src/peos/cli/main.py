"""Argparse CLI with JSON stdout and safe expected errors."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from peos.bootstrap import (
    initialize_workspace,
    mutation_lock,
    open_crossflow_workspace,
    open_evaluation_workspace,
    open_graph_workspace,
    open_learning_workspace,
    open_project_workspace,
    open_protocol_workspace,
    open_research_workspace,
    open_run_for_id,
    open_run_workspace,
    open_workspace,
)
from peos.domain.artifacts.model import StoredArtifact
from peos.domain.errors import PeosError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="peos")
    parser.add_argument("--workspace", default=".")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    protocol = commands.add_parser("protocol").add_subparsers(
        dest="protocol_command", required=True
    )
    protocol.add_parser("list")
    protocol_verify = protocol.add_parser("verify")
    protocol_verify.add_argument("name")
    protocol_verify.add_argument("version")
    artifact = commands.add_parser("artifact").add_subparsers(
        dest="artifact_command", required=True
    )
    create = artifact.add_parser("create")
    create.add_argument("--title", required=True)
    create.add_argument("--body", required=True)
    create.add_argument("--tag", action="append", default=[])
    create.add_argument("--id")
    get = artifact.add_parser("get")
    get.add_argument("artifact_id")
    search = artifact.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=20)
    verify = artifact.add_parser("verify")
    verify.add_argument("artifact_id")
    index = commands.add_parser("index").add_subparsers(dest="index_command", required=True)
    index.add_parser("rebuild")
    run = commands.add_parser("run").add_subparsers(dest="run_command", required=True)
    start = run.add_parser("start")
    start.add_argument("workflow")
    start.add_argument("--input", required=True)
    start.add_argument(
        "--stop-after-step",
        choices=["prepare-derived-concept", "mock-summarize-concept"],
    )
    start.add_argument("--no-cache", action="store_true")
    inspect = run.add_parser("inspect")
    inspect.add_argument("run_id")
    resume = run.add_parser("resume")
    resume.add_argument("run_id")
    cancel = run.add_parser("cancel")
    cancel.add_argument("run_id")
    verify_run = run.add_parser("verify")
    verify_run.add_argument("run_id")
    research = commands.add_parser("research").add_subparsers(
        dest="research_command", required=True
    )
    compile_research = research.add_parser("compile")
    compile_research.add_argument("--question", required=True)
    compile_research.add_argument("--source", action="append", required=True)
    compile_research.add_argument(
        "--stop-after-step",
        choices=["ingest-research-inputs", "extract-candidate-claims"],
    )
    compile_research.add_argument("--no-cache", action="store_true")
    project = commands.add_parser("project").add_subparsers(dest="project_command", required=True)
    compile_project = project.add_parser("compile")
    compile_project.add_argument("--request-file", required=True)
    compile_project.add_argument(
        "--stop-after-step",
        choices=["snapshot-project-inputs", "draft-project-charter"],
    )
    compile_project.add_argument("--no-cache", action="store_true")
    export_project = project.add_parser("export-codex")
    export_project.add_argument("packet_artifact_id")
    accept_project = project.add_parser("accept-result")
    accept_project.add_argument("--packet", required=True)
    accept_project.add_argument("--result-file", required=True)
    learn = commands.add_parser("learn").add_subparsers(dest="learn_command", required=True)
    learn_compile = learn.add_parser("compile")
    learn_compile.add_argument("--goal-file", required=True)
    learn_compile.add_argument("--diagnostic-file", required=True)
    learn_compile.add_argument(
        "--stop-after-step",
        choices=["freeze-learning-inputs", "analyze-learning-gap"],
    )
    learn_attempt = learn.add_parser("attempt")
    learn_attempt.add_argument("--goal", required=True)
    learn_attempt.add_argument("--attempt-file", required=True)
    graph = commands.add_parser("graph")
    graph.add_argument("artifact_id")
    graph.add_argument("--depth", type=int, default=1)
    crossflow = commands.add_parser("crossflow").add_subparsers(
        dest="crossflow_command", required=True
    )
    bridge = crossflow.add_parser("bridge")
    bridge.add_argument("--request-file", required=True)
    bridge.add_argument("--stop-after-step", choices=["resolve-crossflow-inputs"])
    evaluation = commands.add_parser("eval").add_subparsers(dest="eval_command", required=True)
    eval_run = evaluation.add_parser("run")
    eval_run.add_argument("suite_name")
    eval_run.add_argument("--provider", required=True)
    eval_run.add_argument("--model", required=True)
    eval_run.add_argument("--model-revision", required=True)
    eval_compare = evaluation.add_parser("compare")
    eval_compare.add_argument("run_a")
    eval_compare.add_argument("run_b")
    return parser


def _emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _artifact_json(stored: StoredArtifact) -> dict[str, object]:
    artifact = stored.artifact
    result: dict[str, object] = {
        "authors": [{"id": author.id, "kind": author.kind} for author in artifact.authors],
        "body": artifact.body,
        "content_hash": artifact.content_hash,
        "created_at": artifact.created_at,
        "id": artifact.id,
        "links": list(artifact.links),
        "provenance": {
            "producer": artifact.provenance.producer,
            "run_id": artifact.provenance.run_id,
            "source_refs": list(artifact.provenance.source_refs),
        },
        "schema_version": artifact.schema_version,
        "sensitivity": artifact.sensitivity,
        "status": artifact.status,
        "tags": list(artifact.tags),
        "title": artifact.title,
        "type": artifact.type,
        "updated_at": artifact.updated_at,
        "workspace_id": artifact.workspace_id,
    }
    if artifact.payload is not None:
        result["payload"] = artifact.payload
    return result


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    workspace = Path(arguments.workspace).resolve()
    try:
        if arguments.command == "init":
            _, _, workspace_id, created = initialize_workspace(workspace)
            _emit(
                {
                    "status": "initialized" if created else "already_initialized",
                    "workspace": str(workspace),
                    "workspace_id": workspace_id,
                }
            )
            return 0
        artifacts, indexing = open_workspace(workspace)
        if arguments.command == "protocol":
            protocols = open_protocol_workspace(workspace)
            if arguments.protocol_command == "list":
                _emit(
                    [
                        {
                            "name": item.name,
                            "version": item.version,
                            "sha256": item.sha256,
                            "status": item.status,
                            "task_kinds": list(item.task_kinds),
                            "output_contracts": list(item.output_contracts),
                            "sensitivity_ceiling": item.sensitivity_ceiling,
                        }
                        for item in protocols.list()
                    ]
                )
                return 0
            if arguments.protocol_command == "verify":
                item = protocols.get(arguments.name, arguments.version)
                _emit(
                    {
                        "name": item.name,
                        "version": item.version,
                        "sha256": item.sha256,
                        "status": item.status,
                        "valid": True,
                    }
                )
                return 0
        if arguments.command == "artifact" and arguments.artifact_command == "create":
            with mutation_lock(workspace, "artifact create"):
                stored = artifacts.create_concept(
                    arguments.title, arguments.body, arguments.tag, arguments.id
                )
            _emit(
                {
                    "canonical_path": stored.canonical_path,
                    "content_hash": stored.artifact.content_hash,
                    "id": stored.artifact.id,
                    "type": stored.artifact.type,
                }
            )
            return 0
        if arguments.command == "artifact" and arguments.artifact_command == "get":
            _emit(_artifact_json(artifacts.get(arguments.artifact_id)))
            return 0
        if arguments.command == "artifact" and arguments.artifact_command == "search":
            results = artifacts.search(arguments.query, arguments.limit)
            _emit([result.__dict__ for result in results])
            return 0
        if arguments.command == "artifact" and arguments.artifact_command == "verify":
            stored = artifacts.verify(arguments.artifact_id)
            _emit(
                {
                    "content_hash": stored.artifact.content_hash,
                    "id": stored.artifact.id,
                    "valid": True,
                }
            )
            return 0
        if arguments.command == "index" and arguments.index_command == "rebuild":
            with mutation_lock(workspace, "index rebuild"):
                count = indexing.rebuild()
            _emit(
                {
                    "artifacts_indexed": count,
                    "index_path": ".peos/index.sqlite3",
                    "status": "rebuilt",
                }
            )
            return 0
        if arguments.command == "research" and arguments.research_command == "compile":
            with mutation_lock(workspace, "research compile"):
                result = open_research_workspace(workspace).start(
                    arguments.question,
                    arguments.source,
                    arguments.stop_after_step,
                    arguments.no_cache,
                )
            _emit(result)
            return 0
        if arguments.command == "project":
            projects = open_project_workspace(workspace)
            if arguments.project_command == "compile":
                with mutation_lock(workspace, "project compile"):
                    result = projects.start(
                        Path(arguments.request_file),
                        arguments.stop_after_step,
                        arguments.no_cache,
                    )
                _emit(result)
                return 0
            if arguments.project_command == "export-codex":
                _emit(projects.export_packet(arguments.packet_artifact_id))
                return 0
            if arguments.project_command == "accept-result":
                with mutation_lock(workspace, "project accept-result"):
                    result = projects.accept_result(arguments.packet, Path(arguments.result_file))
                _emit(result)
                return 0
        if arguments.command == "learn":
            learning = open_learning_workspace(workspace)
            if arguments.learn_command == "compile":
                with mutation_lock(workspace, "learn compile"):
                    result = learning.start_compile(
                        Path(arguments.goal_file),
                        Path(arguments.diagnostic_file),
                        arguments.stop_after_step,
                    )
                _emit(result)
                return 0
            if arguments.learn_command == "attempt":
                with mutation_lock(workspace, "learn attempt"):
                    result = learning.start_attempt(arguments.goal, Path(arguments.attempt_file))
                _emit(result)
                return 0
        if arguments.command == "graph":
            _emit(open_graph_workspace(workspace).traverse(arguments.artifact_id, arguments.depth))
            return 0
        if arguments.command == "crossflow" and arguments.crossflow_command == "bridge":
            with mutation_lock(workspace, "crossflow bridge"):
                result = open_crossflow_workspace(workspace).start(
                    Path(arguments.request_file), arguments.stop_after_step
                )
            _emit(result)
            return 0
        if arguments.command == "eval":
            evaluations = open_evaluation_workspace(workspace)
            if arguments.eval_command == "run":
                with mutation_lock(workspace, "eval run"):
                    result = evaluations.start(
                        arguments.suite_name,
                        arguments.provider,
                        arguments.model,
                        arguments.model_revision,
                    )
                _emit(result)
                return 0
            if arguments.eval_command == "compare":
                _emit(evaluations.compare(arguments.run_a, arguments.run_b))
                return 0
        if arguments.command == "run":
            if arguments.run_command == "start":
                runs = open_run_workspace(workspace)
                with mutation_lock(workspace, "run start"):
                    result = runs.start(
                        arguments.workflow,
                        arguments.input,
                        arguments.stop_after_step,
                        arguments.no_cache,
                    )
                _emit(result)
                return 0
            if arguments.run_command == "inspect":
                selected_runs = open_run_for_id(workspace, arguments.run_id)
                _emit(selected_runs.inspect(arguments.run_id))
                return 0
            if arguments.run_command == "resume":
                selected_runs = open_run_for_id(workspace, arguments.run_id)
                with mutation_lock(workspace, "run resume"):
                    result = selected_runs.resume(arguments.run_id)
                _emit(result)
                return 0
            if arguments.run_command == "cancel":
                selected_runs = open_run_for_id(workspace, arguments.run_id)
                with mutation_lock(workspace, "run cancel"):
                    result = selected_runs.cancel(arguments.run_id)
                _emit(result)
                return 0
            if arguments.run_command == "verify":
                selected_runs = open_run_for_id(workspace, arguments.run_id)
                _emit(selected_runs.verify(arguments.run_id))
                return 0
        parser.error("Unknown command.")
    except PeosError as error:
        suffix = f" Recovery: {error.recovery_action}" if error.recovery_action else ""
        print(f"{error.code}: {error.message}{suffix}", file=sys.stderr)
        return error.exit_code
    except Exception:
        if os.environ.get("PEOS_DEBUG") == "1":
            raise
        print("internal_error: PEOS command failed unexpectedly.", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
