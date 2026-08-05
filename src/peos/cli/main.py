"""Argparse CLI with JSON stdout and safe expected errors."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from peos.bootstrap import initialize_workspace, open_workspace
from peos.domain.artifacts.model import StoredArtifact
from peos.domain.errors import PeosError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="peos")
    parser.add_argument("--workspace", default=".")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
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
    return parser


def _emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _artifact_json(stored: StoredArtifact) -> dict[str, object]:
    artifact = stored.artifact
    return {
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
        if arguments.command == "artifact" and arguments.artifact_command == "create":
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
            count = indexing.rebuild()
            _emit(
                {
                    "artifacts_indexed": count,
                    "index_path": ".peos/index.sqlite3",
                    "status": "rebuilt",
                }
            )
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
