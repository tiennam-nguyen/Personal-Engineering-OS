"""Strict directory backups, canonical inventory, restore, GC, and doctor storage."""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from peos.adapters.filesystem.evaluation_repository import FilesystemEvaluationSuiteRepository
from peos.adapters.filesystem.protocol_repository import FilesystemProtocolRepository
from peos.adapters.filesystem.repository import FilesystemArtifactRepository
from peos.adapters.filesystem.run_repository import FilesystemRunRepository
from peos.adapters.filesystem.workspace import Workspace, WorkspaceStore
from peos.adapters.filesystem.workspace_lock import lock_is_active
from peos.adapters.sqlite.artifact_index import SQLiteArtifactIndex
from peos.application.indexing import IndexingService
from peos.domain.errors import (
    BackupConflictError,
    GarbageCollectionBlockedError,
    HardeningIntegrityError,
)
from peos.domain.hardening import (
    InventoryEntry,
    WorkspaceInventory,
    entry_mapping,
    inventory_generation,
    sha256_bytes,
    validate_relative_path,
)
from peos.domain.relations.model import materialize_links
from peos.domain.runs.model import canonical_json, sha256
from peos.ports.fault_injector import FaultInjector, NoOpFaultInjector
from peos.workflows.registry import get as get_workflow

APPLICATION_VERSION = "1.0.0"
BACKUP_FORMAT_VERSION = 1
MANIFEST_KEYS = {
    "format_version",
    "backup_id",
    "created_at",
    "source_workspace_id",
    "source_generation",
    "application_version",
    "self_contained",
    "files",
    "object_manifest",
}
FILE_KEYS = {"path", "classification", "size_bytes", "sha256"}
OBJECT_KEYS = {"object_hash", "path", "size_bytes", "referenced_status"}
OBJECT_MANIFEST_KEYS = {"format_version", "objects"}
FORBIDDEN_PREFIXES = (
    ".peos/cache/",
    ".peos/locks/",
    ".peos/staging/",
    ".peos/backups/",
    ".peos/quarantine/",
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _json(raw: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HardeningIntegrityError(f"{label} is not strict JSON.") from error
    if not isinstance(value, dict):
        raise HardeningIntegrityError(f"{label} is invalid.")
    return cast(dict[str, object], value)


def _classification(relative: str) -> str | None:
    if relative == "peos.yaml":
        return "workspace_config"
    if relative in {"MAP.md", "PLAN.md"}:
        return relative.removesuffix(".md").lower()
    prefixes = (
        ("artifacts/", "artifact"),
        ("protocols/", "protocol"),
        ("evals/", "eval"),
        ("workflows/", "workflow_config"),
        ("adr/", "adr"),
        (".peos/migrations/records/", "migration_record"),
        (".peos/objects/", "object_blob"),
    )
    for prefix, classification in prefixes:
        if relative.startswith(prefix):
            return classification
    if relative.startswith(".peos/runs/"):
        name = Path(relative).name
        if name == "manifest.json":
            return "run_manifest"
        if name == "events.jsonl":
            return "run_journal"
        if name == "inputs.json":
            return "run_inputs"
        if name == "outputs.json":
            return "run_outputs"
        if "/evidence/" in relative:
            return "run_evidence"
    return None


class FilesystemHardeningRepository:
    def __init__(self, workspace: Workspace, faults: FaultInjector | None = None) -> None:
        self._workspace = workspace
        self._faults = faults or NoOpFaultInjector()

    def inventory(self) -> WorkspaceInventory:
        entries: list[InventoryEntry] = []
        for path in sorted(self._workspace.root.rglob("*")):
            relative = path.relative_to(self._workspace.root).as_posix()
            classification = _classification(relative)
            if classification is None:
                continue
            if path.is_symlink():
                raise HardeningIntegrityError("Canonical inventory cannot contain symlinks.")
            if not path.is_file():
                continue
            resolved = path.resolve()
            if self._workspace.root != resolved and self._workspace.root not in resolved.parents:
                raise HardeningIntegrityError("Canonical inventory path escapes workspace.")
            raw = path.read_bytes()
            entries.append(InventoryEntry(relative, classification, len(raw), sha256_bytes(raw)))
        ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
        if not any(item.relative_path == "peos.yaml" for item in ordered):
            raise HardeningIntegrityError("Workspace inventory lacks peos.yaml.")
        return WorkspaceInventory(
            self._workspace.workspace_id, ordered, inventory_generation(ordered)
        )

    def create_backup(self, output: Path | None, dry_run: bool) -> dict[str, object]:
        inventory = self.inventory()
        backup_id = "bkp_" + uuid.uuid4().hex
        destination = (
            output.resolve()
            if output is not None
            else (self._workspace.operational_root / "backups" / backup_id).resolve()
        )
        if destination.exists():
            raise BackupConflictError("Backup destination already exists.")
        result = {
            "backup_id": backup_id,
            "destination": str(destination),
            "source_workspace_id": inventory.workspace_id,
            "source_generation": inventory.generation,
            "file_count": len(inventory.entries),
            "dry_run": dry_run,
        }
        if dry_run:
            return result
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = destination.with_name(f".{destination.name}.staging-{uuid.uuid4().hex}")
        staging.mkdir()
        visible = False
        try:
            self._faults.checkpoint("after_backup_inventory")
            payload = staging / "payload"
            objects: list[dict[str, object]] = []
            for ordinal, entry in enumerate(inventory.entries, 1):
                source = self._workspace.root / entry.relative_path
                target = payload / entry.relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.is_symlink():
                    raise HardeningIntegrityError("Backup source became a symlink.")
                _write_new(target, source.read_bytes())
                if sha256_bytes(target.read_bytes()) != entry.sha256:
                    raise HardeningIntegrityError("Copied backup payload checksum differs.")
                if entry.classification == "object_blob":
                    objects.append(
                        {
                            "object_hash": "sha256:" + Path(entry.relative_path).name,
                            "path": entry.relative_path,
                            "size_bytes": entry.byte_size,
                            "referenced_status": "included_self_contained",
                        }
                    )
                if ordinal == 1:
                    self._faults.checkpoint("during_backup_payload_copy")
            self._faults.checkpoint("after_backup_payload_copy")
            object_manifest = {"format_version": 1, "objects": objects}
            _write_new(staging / "objects.json", canonical_json(object_manifest) + b"\n")
            manifest = {
                "format_version": BACKUP_FORMAT_VERSION,
                "backup_id": backup_id,
                "created_at": _now(),
                "source_workspace_id": inventory.workspace_id,
                "source_generation": inventory.generation,
                "application_version": APPLICATION_VERSION,
                "self_contained": True,
                "files": [entry_mapping(entry) for entry in inventory.entries],
                "object_manifest": "objects.json",
            }
            _write_new(staging / "manifest.json", canonical_json(manifest) + b"\n")
            self._faults.checkpoint("after_backup_manifest")
            staging.replace(destination)
            visible = True
            self._faults.checkpoint("after_backup_visible")
            return {**result, **verify_backup(destination)}
        finally:
            if not visible and staging.exists():
                shutil.rmtree(staging)

    def gc_plan(self) -> dict[str, object]:
        inventory = self.inventory()
        policy = self._workspace.retention
        referenced = self._referenced_hashes()
        candidates: list[dict[str, object]] = []
        retained: list[dict[str, object]] = []
        now = datetime.now(UTC).timestamp()
        object_root = self._workspace.objects_root
        for path in sorted(object_root.rglob("*")) if object_root.exists() else []:
            if not path.is_file() or path.is_symlink():
                continue
            object_hash = "sha256:" + path.name
            item = {
                "path": path.relative_to(self._workspace.root).as_posix(),
                "sha256": object_hash,
            }
            if object_hash in referenced:
                retained.append({**item, "reason": "referenced_for_verification"})
            else:
                candidates.append({**item, "reason": "proven_orphan_object"})
        cache_root = self._workspace.operational_root / "cache"
        for path in sorted(cache_root.rglob("*")) if cache_root.exists() else []:
            if not path.is_file() or path.is_symlink():
                continue
            item = {
                "path": path.relative_to(self._workspace.root).as_posix(),
                "sha256": sha256_bytes(path.read_bytes()),
            }
            age_days = (now - path.stat().st_mtime) / 86400
            target = candidates if age_days > policy.cache_days else retained
            target.append(
                {
                    **item,
                    "reason": "expired_derived_cache" if target is candidates else "current_cache",
                }
            )
        plan_id = "gc_" + uuid.uuid4().hex
        content = {
            "schema_version": 1,
            "plan_id": plan_id,
            "workspace_id": inventory.workspace_id,
            "workspace_generation": inventory.generation,
            "retention": policy.__dict__,
            "created_at": _now(),
            "retained": retained,
            "candidates": candidates,
            "total_candidate_bytes": sum(
                (self._workspace.root / str(item["path"])).stat().st_size for item in candidates
            ),
        }
        sealed = {**content, "plan_hash": sha256(content)}
        path = self._workspace.operational_root / "gc" / "plans" / f"{plan_id}.json"
        _write_new(path, json.dumps(sealed, sort_keys=True, indent=2).encode() + b"\n")
        return sealed

    def gc_execute(
        self, plan_id: str, backup: Path, confirmed: bool, dry_run: bool
    ) -> dict[str, object]:
        if not confirmed:
            raise GarbageCollectionBlockedError("GC execution requires explicit confirmation.")
        path = self._workspace.operational_root / "gc" / "plans" / f"{plan_id}.json"
        plan = _json(path.read_bytes(), "GC plan")
        plan_hash = plan.pop("plan_hash", None)
        if plan_hash != sha256(plan):
            raise GarbageCollectionBlockedError("GC plan hash is invalid.")
        existing_record = (
            self._workspace.operational_root / "quarantine" / plan_id / "execution.json"
        )
        if existing_record.exists():
            return _json(existing_record.read_bytes(), "GC execution record")
        inventory = self.inventory()
        if plan.get("workspace_generation") != inventory.generation:
            raise GarbageCollectionBlockedError(
                "GC plan is stale for current workspace generation."
            )
        verified = verify_backup(backup)
        if (
            verified["source_workspace_id"] != inventory.workspace_id
            or verified["source_generation"] != inventory.generation
        ):
            raise GarbageCollectionBlockedError("GC backup does not match current generation.")
        candidates = cast(list[object], plan.get("candidates"))
        referenced = self._referenced_hashes()
        moves: list[dict[str, object]] = []
        for value in candidates:
            if not isinstance(value, dict):
                raise GarbageCollectionBlockedError("GC candidate is invalid.")
            relative = validate_relative_path(str(value["path"]))
            if str(value["sha256"]) in referenced:
                raise GarbageCollectionBlockedError("GC candidate became referenced.")
            source = self._workspace.root / relative
            if source.exists() and sha256_bytes(source.read_bytes()) != value["sha256"]:
                raise GarbageCollectionBlockedError("GC candidate bytes changed.")
            moves.append({"path": relative, "sha256": value["sha256"]})
        if dry_run:
            return {"plan_id": plan_id, "dry_run": True, "moves": moves}
        quarantine = self._workspace.operational_root / "quarantine" / plan_id
        completed: list[dict[str, object]] = []
        quarantine.mkdir(parents=True, exist_ok=True)
        for item in moves:
            source = self._workspace.root / str(item["path"])
            target = quarantine / str(item["path"])
            if not source.exists():
                if target.exists() and sha256_bytes(target.read_bytes()) == item["sha256"]:
                    completed.append(item)
                    continue
                raise GarbageCollectionBlockedError("GC candidate is missing.")
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)
            if sha256_bytes(target.read_bytes()) != item["sha256"]:
                raise GarbageCollectionBlockedError("Quarantined candidate checksum differs.")
            completed.append(item)
        record = {
            "schema_version": 1,
            "plan_id": plan_id,
            "completed_at": _now(),
            "quarantine_until": (
                datetime.now(UTC) + timedelta(days=self._workspace.retention.quarantine_days)
            )
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "moves": completed,
            "permanent_delete": False,
        }
        record_path = quarantine / "execution.json"
        if not record_path.exists():
            _write_new(record_path, json.dumps(record, sort_keys=True, indent=2).encode() + b"\n")
        return record

    def doctor(self) -> dict[str, object]:
        checks: list[dict[str, object]] = []

        def check(name: str, operation: object, recovery: str | None = None) -> None:
            try:
                detail = operation() if callable(operation) else operation
                checks.append({"name": name, "status": "PASS", "detail": str(detail)})
            except Exception as error:
                value: dict[str, object] = {
                    "name": name,
                    "status": "FAIL",
                    "code": type(error).__name__,
                    "detail": str(error),
                }
                if recovery:
                    value["recovery"] = recovery
                checks.append(value)

        store = WorkspaceStore()
        repository = FilesystemArtifactRepository(self._workspace, store)
        index = SQLiteArtifactIndex(self._workspace.index_path)
        run_repository = FilesystemRunRepository(self._workspace)
        check(
            "configuration",
            lambda: store.open(self._workspace.root, ensure_layout=False).workspace_id,
        )
        check("canonical_inventory", lambda: self.inventory().generation)
        check("canonical_artifacts", lambda: len(repository.scan()))
        check("canonical_relations", lambda: self._verify_relations(repository))
        check(
            "run_journals",
            lambda: self._verify_run_journals(run_repository),
        )
        check("run_workflow_versions", lambda: self._verify_workflows(run_repository))
        check("object_blobs", self._verify_objects)
        check("object_references", self._verify_object_references)
        check(
            "derived_index",
            lambda: self._verify_index(repository, index),
            f"peos --workspace {self._workspace.root} index rebuild",
        )
        check("migration_records", self._verify_migration_records)
        check(
            "protocol_versions",
            lambda: (
                len(FilesystemProtocolRepository(self._workspace.root).list())
                if (self._workspace.root / "protocols/registry.yaml").exists()
                else 0
            ),
        )
        check(
            "evaluation_suites",
            lambda: (
                len(FilesystemEvaluationSuiteRepository(self._workspace.root).list_active())
                if (self._workspace.root / "evals/registry.yaml").exists()
                else 0
            ),
        )
        check(
            "evaluation_qualification_sources",
            lambda: self._verify_eval_sources(repository, run_repository),
        )
        check("secret_control_surfaces", self._secret_scan)
        check("lock_state", self._lock_check)
        inventory = self.inventory()
        return {
            "healthy": not any(item["status"] == "FAIL" for item in checks),
            "workspace_generation": inventory.generation,
            "checks": checks,
        }

    def _referenced_hashes(self) -> set[str]:
        references: set[str] = set()
        for entry in self.inventory().entries:
            if entry.classification == "object_blob":
                continue
            raw = (self._workspace.root / entry.relative_path).read_bytes()
            text = raw.decode("utf-8", errors="ignore")
            references.update(re.findall(r"sha256:[0-9a-f]{64}", text))
        return references

    def _verify_objects(self) -> int:
        count = 0
        for path in self._workspace.objects_root.rglob("*"):
            if path.is_file():
                if path.is_symlink() or sha256_bytes(path.read_bytes()) != "sha256:" + path.name:
                    raise HardeningIntegrityError("Source object hash is invalid.")
                count += 1
        return count

    def _verify_relations(self, repository: FilesystemArtifactRepository) -> int:
        records = repository.scan()
        ids = {item.artifact.id for item in records}
        count = 0
        for item in records:
            for edge in materialize_links(
                item.artifact.id, item.artifact.links, item.artifact.content_hash
            ):
                if edge.source_artifact_id not in ids or edge.target_artifact_id not in ids:
                    raise HardeningIntegrityError("Canonical relation endpoint is missing.")
                count += 1
        return count

    def _verify_index(
        self,
        repository: FilesystemArtifactRepository,
        index: SQLiteArtifactIndex,
    ) -> str:
        if not index.is_healthy():
            raise HardeningIntegrityError("Derived index is missing, dirty, or incompatible.")
        expected_edges: set[tuple[str, str, str, str, str | None]] = set()
        actual_edges: set[tuple[str, str, str, str, str | None]] = set()
        for stored in repository.scan():
            projected = index.get(stored.artifact.id)
            if (
                projected.canonical_path != stored.canonical_path
                or projected.artifact.content_hash != stored.artifact.content_hash
            ):
                raise HardeningIntegrityError("Derived artifact projection diverges.")
            for edge in materialize_links(
                stored.artifact.id, stored.artifact.links, stored.artifact.content_hash
            ):
                expected_edges.add(
                    (
                        edge.source_artifact_id,
                        edge.relation,
                        edge.target_artifact_id,
                        edge.host_artifact_id,
                        edge.host_revision,
                    )
                )
            for edge in index.outgoing(stored.artifact.id):
                actual_edges.add(
                    (
                        edge.source_artifact_id,
                        edge.relation,
                        edge.target_artifact_id,
                        edge.host_artifact_id,
                        edge.host_revision,
                    )
                )
        if expected_edges != actual_edges:
            raise HardeningIntegrityError("Derived relation projection diverges.")
        return f"{len(repository.scan())} artifacts and {len(expected_edges)} relations current"

    def _verify_workflows(self, runs: FilesystemRunRepository) -> int:
        count = 0
        for path in sorted(self._workspace.runs_root.iterdir()):
            if not path.is_dir():
                continue
            workflow = runs.read_manifest(path.name).get("workflow")
            if not isinstance(workflow, dict):
                raise HardeningIntegrityError("Run workflow reference is invalid.")
            definition = get_workflow(str(workflow.get("name")))
            if definition.version != workflow.get("version"):
                raise HardeningIntegrityError("Run workflow version is unavailable.")
            count += 1
        return count

    def _verify_run_journals(self, runs: FilesystemRunRepository) -> int:
        count = 0
        for path in sorted(self._workspace.runs_root.iterdir()):
            if not path.is_dir():
                continue
            runs.events(path.name)
            count += 1
        return count

    def _verify_object_references(self) -> int:
        referenced = self._structured_object_hashes()
        for object_hash in referenced:
            digest = object_hash.removeprefix("sha256:")
            path = self._workspace.objects_root / digest[:2] / digest
            if not path.is_file() or sha256_bytes(path.read_bytes()) != object_hash:
                raise HardeningIntegrityError("Referenced source object is missing or corrupt.")
        return len(referenced)

    def _structured_object_hashes(self) -> set[str]:
        found: set[str] = set()

        def visit(value: object) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "object_hash" and isinstance(item, str):
                        found.add(item)
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        for entry in self.inventory().entries:
            if entry.classification not in {
                "artifact",
                "run_manifest",
                "run_inputs",
                "run_outputs",
                "run_evidence",
            }:
                continue
            path = self._workspace.root / entry.relative_path
            if path.suffix == ".json":
                try:
                    visit(json.loads(path.read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    continue
            else:
                text = path.read_text(encoding="utf-8", errors="ignore")
                found.update(re.findall(r"object_hash:\s*(sha256:[0-9a-f]{64})", text))
        return found

    def _verify_eval_sources(
        self,
        repository: FilesystemArtifactRepository,
        runs: FilesystemRunRepository,
    ) -> int:
        count = 0
        for stored in repository.scan():
            if stored.artifact.type != "system.eval_report":
                continue
            run_id = stored.artifact.provenance.run_id
            if run_id is None:
                raise HardeningIntegrityError("Evaluation report has no source run.")
            events = runs.events(run_id)
            outputs = runs.read_outputs(run_id)
            if not events or events[-1].type != "run.succeeded" or not outputs:
                raise HardeningIntegrityError("Evaluation report source run is not succeeded.")
            output_values = cast(list[object], outputs.get("artifacts", []))
            if not any(
                isinstance(value, dict)
                and value.get("id") == stored.artifact.id
                and value.get("content_hash") == stored.artifact.content_hash
                for value in output_values
            ):
                raise HardeningIntegrityError("Evaluation report source outputs conflict.")
            count += 1
        return count

    def _verify_migration_records(self) -> int:
        root = self._workspace.operational_root / "migrations" / "records"
        count = 0
        for path in sorted(root.glob("*.json")) if root.exists() else []:
            value = _json(path.read_bytes(), "Migration record")
            record_hash = value.pop("record_hash", None)
            if record_hash != sha256(value):
                raise HardeningIntegrityError("Migration record hash is invalid.")
            count += 1
        return count

    def _secret_scan(self) -> str:
        patterns = ("BEGIN PRIVATE KEY", "aws_secret_access_key", "secret_value")
        config = (self._workspace.root / "peos.yaml").read_text(encoding="utf-8")
        if any(pattern.casefold() in config.casefold() for pattern in patterns):
            raise HardeningIntegrityError("Potential secret found in PEOS control configuration.")
        return "no high-confidence control-plane match"

    def _lock_check(self) -> str:
        lock = self._workspace.locks_root / "workspace.lock"
        if lock_is_active(lock):
            raise HardeningIntegrityError("Workspace mutation lock is active.")
        return "no active mutation"


def verify_backup(root: Path) -> dict[str, object]:
    root = root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise HardeningIntegrityError("Backup root must be a real directory.")
    manifest_path, objects_path, payload = (
        root / "manifest.json",
        root / "objects.json",
        root / "payload",
    )
    for required in (manifest_path, objects_path, payload):
        if not required.exists() or required.is_symlink():
            raise HardeningIntegrityError("Backup required path is missing or a symlink.")
    manifest = _json(manifest_path.read_bytes(), "Backup manifest")
    if set(manifest) != MANIFEST_KEYS or manifest["format_version"] != BACKUP_FORMAT_VERSION:
        raise HardeningIntegrityError("Backup manifest fields or format are unsupported.")
    backup_id = manifest["backup_id"]
    if not isinstance(backup_id, str) or not backup_id.startswith("bkp_") or len(backup_id) != 36:
        raise HardeningIntegrityError("Backup ID is invalid.")
    if manifest["object_manifest"] != "objects.json" or manifest["self_contained"] is not True:
        raise HardeningIntegrityError("Backup object policy is invalid.")
    files = manifest["files"]
    if not isinstance(files, list) or not files:
        raise HardeningIntegrityError("Backup file list is invalid.")
    entries: list[InventoryEntry] = []
    listed: set[str] = set()
    for value in files:
        if not isinstance(value, dict) or set(value) != FILE_KEYS:
            raise HardeningIntegrityError("Backup file entry is invalid.")
        relative = validate_relative_path(str(value["path"]))
        if relative.casefold() in {item.casefold() for item in listed}:
            raise HardeningIntegrityError("Backup has duplicate normalized paths.")
        if relative.startswith(FORBIDDEN_PREFIXES) or relative in {".env", ".peos/index.sqlite3"}:
            raise HardeningIntegrityError("Backup lists forbidden derived or secret state.")
        target = payload / relative
        if not target.is_file() or target.is_symlink() or payload not in target.resolve().parents:
            raise HardeningIntegrityError(
                "Backup payload file is missing, unsafe, or outside root."
            )
        raw = target.read_bytes()
        entry = InventoryEntry(
            relative,
            str(value["classification"]),
            int(cast(int, value["size_bytes"])),
            str(value["sha256"]),
        )
        if len(raw) != entry.byte_size or sha256_bytes(raw) != entry.sha256:
            raise HardeningIntegrityError("Backup payload size or checksum differs.")
        entries.append(entry)
        listed.add(relative)
    actual = {
        path.relative_to(payload).as_posix()
        for path in payload.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if actual != listed or any(path.is_symlink() for path in payload.rglob("*")):
        raise HardeningIntegrityError("Backup payload contains unlisted or symlink entries.")
    objects = _json(objects_path.read_bytes(), "Object manifest")
    if set(objects) != OBJECT_MANIFEST_KEYS or objects["format_version"] != 1:
        raise HardeningIntegrityError("Object manifest is invalid.")
    object_values = objects["objects"]
    if not isinstance(object_values, list):
        raise HardeningIntegrityError("Object list is invalid.")
    for value in object_values:
        if not isinstance(value, dict) or set(value) != OBJECT_KEYS:
            raise HardeningIntegrityError("Object manifest entry is invalid.")
        relative = validate_relative_path(str(value["path"]))
        object_hash = str(value["object_hash"])
        raw = (payload / relative).read_bytes()
        if (
            relative not in listed
            or object_hash != "sha256:" + Path(relative).name
            or sha256_bytes(raw) != object_hash
            or len(raw) != value["size_bytes"]
        ):
            raise HardeningIntegrityError("Backup object bytes or digest are invalid.")
    generation = inventory_generation(tuple(entries))
    if generation != manifest["source_generation"] or "peos.yaml" not in listed:
        raise HardeningIntegrityError("Backup source generation or workspace config is invalid.")
    return {
        "valid": True,
        "backup_id": backup_id,
        "source_workspace_id": manifest["source_workspace_id"],
        "source_generation": generation,
        "file_count": len(entries),
        "object_count": len(object_values),
        "total_bytes": sum(entry.byte_size for entry in entries),
        "manifest_hash": sha256_bytes(manifest_path.read_bytes()),
    }


def restore_backup(
    backup: Path, target: Path, dry_run: bool, faults: FaultInjector | None = None
) -> dict[str, object]:
    verified = verify_backup(backup)
    target = target.resolve()
    if target.exists():
        raise BackupConflictError("Restore target already exists; overwrite is forbidden.")
    result = {**verified, "restored_workspace": str(target), "dry_run": dry_run}
    if dry_run:
        return result
    injector = faults or NoOpFaultInjector()
    injector.checkpoint("after_restore_backup_verified")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f".{target.name}.restore-{uuid.uuid4().hex}")
    staging.mkdir()
    visible = False
    try:
        manifest = _json((backup / "manifest.json").read_bytes(), "Backup manifest")
        for ordinal, value in enumerate(cast(list[dict[str, object]], manifest["files"]), 1):
            relative = validate_relative_path(str(value["path"]))
            source, destination = backup / "payload" / relative, staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            _write_new(destination, source.read_bytes())
            if ordinal == 1:
                injector.checkpoint("during_restore_staging_copy")
        injector.checkpoint("after_restore_copy")
        workspace = WorkspaceStore().open(staging)
        restored_inventory = FilesystemHardeningRepository(workspace).inventory()
        if restored_inventory.generation != verified["source_generation"]:
            raise HardeningIntegrityError("Restored canonical generation differs from backup.")
        injector.checkpoint("after_restore_generation_verified")
        staging.replace(target)
        visible = True
        injector.checkpoint("after_restore_target_visible")
        workspace = WorkspaceStore().open(target)
        repository = FilesystemArtifactRepository(workspace, WorkspaceStore())
        indexed = IndexingService(repository, SQLiteArtifactIndex(workspace.index_path)).rebuild()
        injector.checkpoint("after_restore_index_rebuilt")
        doctor = FilesystemHardeningRepository(workspace).doctor()
        if not doctor["healthy"]:
            recovery = f"peos --workspace {target} index rebuild"
            raise HardeningIntegrityError(
                f"Canonical restore succeeded but doctor failed. Recovery: {recovery}"
            )
        return {
            **result,
            "restored_generation": restored_inventory.generation,
            "artifacts_indexed": indexed,
            "doctor": doctor,
        }
    finally:
        if not visible and staging.exists():
            shutil.rmtree(staging)
