"""Filesystem implementation of immutable run files and append-only journal."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from peos.adapters.filesystem.workspace import Workspace
from peos.domain.errors import JournalCorruptionError, RunConflictError, RunNotFound
from peos.domain.runs.events import event_mapping, verify_events
from peos.domain.runs.model import Event, canonical_json, sha256


class FilesystemRunRepository:
    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def create(self, manifest: dict[str, object], inputs: dict[str, object]) -> None:
        run_id = manifest.get("run_id")
        if not isinstance(run_id, str):
            raise RunConflictError("Run manifest has no run ID.")
        root = self._workspace.runs_root / run_id
        if root.exists():
            raise RunConflictError("Run ID already exists.")
        root.mkdir(parents=True)
        (root / "evidence").mkdir()
        self._write_new(root / "manifest.json", manifest)
        self._write_new(root / "inputs.json", inputs)
        self._write_new_bytes(root / "events.jsonl", b"")

    def read_manifest(self, run_id: str) -> dict[str, object]:
        return self._read_json(self._root(run_id) / "manifest.json")

    def read_inputs(self, run_id: str) -> dict[str, object]:
        return self._read_json(self._root(run_id) / "inputs.json")

    def events(self, run_id: str) -> list[Event]:
        path = self._root(run_id) / "events.jsonl"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise RunNotFound("Run journal was not found.") from error
        if text and not text.endswith("\n"):
            raise JournalCorruptionError("Journal final newline is missing.")
        lines = text.splitlines()
        if any(not line.strip() for line in lines):
            raise JournalCorruptionError("Journal contains a blank JSONL line.")
        events: list[Event] = []
        for line in lines:
            try:
                item = json.loads(line)
            except json.JSONDecodeError as error:
                raise JournalCorruptionError("Journal JSONL is partial or malformed.") from error
            if not isinstance(item, dict) or set(item) != {
                "schema_version",
                "sequence",
                "event_id",
                "occurred_at",
                "type",
                "run_id",
                "step_id",
                "actor",
                "payload",
                "previous_event_hash",
                "event_hash",
            }:
                raise JournalCorruptionError("Journal event fields are invalid.")
            events.append(Event(**item))
        manifest = self.read_manifest(run_id)
        steps = manifest.get("steps")
        if not isinstance(steps, list):
            raise JournalCorruptionError("Run manifest steps are invalid.")
        step_ids = tuple(
            str(step["step_id"])
            for step in steps
            if isinstance(step, dict) and isinstance(step.get("step_id"), str)
        )
        if len(step_ids) != len(steps):
            raise JournalCorruptionError("Run manifest step IDs are invalid.")
        verify_events(events, step_ids)
        return events

    def append(self, run_id: str, event: Event) -> None:
        events = self.events(run_id)
        if events and events[-1].type in {"run.succeeded", "run.failed", "run.cancelled"}:
            raise RunConflictError("Terminal run journal cannot mutate.")
        if event.sequence != len(events) + 1:
            raise JournalCorruptionError("Journal sequence is not contiguous.")
        verify_events(events + [event])
        path = self._root(run_id) / "events.jsonl"
        encoded = canonical_json(event_mapping(event)) + b"\n"
        with path.open("ab") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        self.events(run_id)

    def write_evidence(self, run_id: str, name: str, envelope: dict[str, object]) -> None:
        path = self._root(run_id) / "evidence" / name
        expected = self._sealed(envelope)
        if path.exists():
            if self._read_json(path) != expected:
                raise RunConflictError("Evidence conflicts with existing immutable evidence.")
            return
        self._write_new(path, expected)

    def read_evidence(self, run_id: str, name: str) -> dict[str, object]:
        result = self._read_json(self._root(run_id) / "evidence" / name)
        content_hash = result.pop("content_hash", None)
        if content_hash != sha256(result):
            raise JournalCorruptionError("Evidence hash is invalid.")
        result["content_hash"] = content_hash
        return result

    def write_outputs(self, run_id: str, outputs: dict[str, object]) -> None:
        path = self._root(run_id) / "outputs.json"
        if path.exists():
            if self._read_json(path) != outputs:
                raise RunConflictError("Outputs conflict with terminal outputs.")
            return
        self._write_new(path, outputs)

    def read_outputs(self, run_id: str) -> dict[str, object] | None:
        path = self._root(run_id) / "outputs.json"
        return self._read_json(path) if path.exists() else None

    def _root(self, run_id: str) -> Path:
        path = self._workspace.runs_root / run_id
        if not path.exists():
            raise RunNotFound("Run was not found.")
        return path

    def _sealed(self, envelope: dict[str, object]) -> dict[str, object]:
        return {**envelope, "content_hash": sha256(envelope)}

    @staticmethod
    def _read_json(path: Path) -> dict[str, object]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise JournalCorruptionError("Immutable run JSON cannot be read.") from error
        if not isinstance(value, dict):
            raise JournalCorruptionError("Immutable run JSON is invalid.")
        return value

    def _write_new(self, path: Path, value: dict[str, object]) -> None:
        self._write_new_bytes(
            path,
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n",
        )

    @staticmethod
    def _write_new_bytes(path: Path, data: bytes) -> None:
        stage = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        with stage.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            stage.unlink()
            raise RunConflictError("Immutable run file already exists.")
        os.replace(stage, path)
