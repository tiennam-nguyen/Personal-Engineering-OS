"""Milestone 1 workspace layout and configuration."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from peos.adapters.filesystem.atomic import atomic_write
from peos.domain.artifacts.validation import validate_workspace_id
from peos.domain.errors import (
    HardeningIntegrityError,
    WorkspaceConfigurationError,
    WorkspaceNotFound,
)
from peos.domain.hardening import RetentionPolicy


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Workspace:
    root: Path
    workspace_id: str
    retention: RetentionPolicy = RetentionPolicy()

    @property
    def artifact_root(self) -> Path:
        return self.root / "artifacts" / "knowledge"

    @property
    def operational_root(self) -> Path:
        return self.root / ".peos"

    @property
    def staging_root(self) -> Path:
        return self.operational_root / "staging"

    @property
    def index_path(self) -> Path:
        return self.operational_root / "index.sqlite3"

    @property
    def dirty_path(self) -> Path:
        return self.operational_root / "INDEX_DIRTY"

    @property
    def runs_root(self) -> Path:
        return self.operational_root / "runs"

    @property
    def locks_root(self) -> Path:
        return self.operational_root / "locks"

    @property
    def objects_root(self) -> Path:
        return self.operational_root / "objects" / "sha256"


class WorkspaceStore:
    def initialize(self, root: Path) -> tuple[Workspace, bool]:
        root = root.resolve()
        config_path = root / "peos.yaml"
        if config_path.exists():
            workspace = self.open(root)
            self._ensure_layout(workspace)
            return workspace, False
        root.mkdir(parents=True, exist_ok=True)
        workspace = Workspace(root=root, workspace_id=f"ws_{uuid.uuid4().hex}")
        self._ensure_layout(workspace)
        config = {
            "schema_version": 1,
            "workspace_id": workspace.workspace_id,
            "created_at": utc_timestamp(),
            "retention": {
                "raw_model_payload_days": workspace.retention.raw_model_payload_days,
                "cache_days": workspace.retention.cache_days,
                "keep_failed_run_evidence": workspace.retention.keep_failed_run_evidence,
                "quarantine_days": workspace.retention.quarantine_days,
            },
        }
        encoded = yaml.safe_dump(
            config, sort_keys=False, allow_unicode=True, default_flow_style=False
        ).encode("utf-8")
        atomic_write(workspace.staging_root, config_path, encoded)
        return workspace, True

    def open(self, root: Path, *, ensure_layout: bool = True) -> Workspace:
        root = root.resolve()
        config_path = root / "peos.yaml"
        if not config_path.exists():
            raise WorkspaceNotFound("Workspace configuration peos.yaml was not found.")
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise WorkspaceConfigurationError("Workspace configuration cannot be read.") from error
        if not isinstance(data, dict) or set(data) not in (
            {"schema_version", "workspace_id", "created_at"},
            {"schema_version", "workspace_id", "created_at", "retention"},
        ):
            raise WorkspaceConfigurationError("Workspace configuration is incompatible.")
        if data["schema_version"] != 1 or not isinstance(data["workspace_id"], str):
            raise WorkspaceConfigurationError("Workspace configuration is incompatible.")
        try:
            validate_workspace_id(data["workspace_id"])
            datetime.fromisoformat(str(data["created_at"]).replace("Z", "+00:00"))
        except (ValueError, WorkspaceConfigurationError) as error:
            raise WorkspaceConfigurationError("Workspace configuration is invalid.") from error
        retention = RetentionPolicy()
        if "retention" in data:
            raw_retention = data["retention"]
            keys = {
                "raw_model_payload_days",
                "cache_days",
                "keep_failed_run_evidence",
                "quarantine_days",
            }
            if not isinstance(raw_retention, dict) or set(raw_retention) != keys:
                raise WorkspaceConfigurationError("Workspace retention configuration is invalid.")
            if not all(
                isinstance(raw_retention[key], int) and not isinstance(raw_retention[key], bool)
                for key in (
                    "raw_model_payload_days",
                    "cache_days",
                    "quarantine_days",
                )
            ) or not isinstance(raw_retention["keep_failed_run_evidence"], bool):
                raise WorkspaceConfigurationError("Workspace retention configuration is invalid.")
            try:
                retention = RetentionPolicy(
                    int(raw_retention["raw_model_payload_days"]),
                    int(raw_retention["cache_days"]),
                    raw_retention["keep_failed_run_evidence"],
                    int(raw_retention["quarantine_days"]),
                )
            except (TypeError, ValueError, HardeningIntegrityError) as error:
                raise WorkspaceConfigurationError(
                    "Workspace retention configuration is invalid."
                ) from error
        workspace = Workspace(root=root, workspace_id=data["workspace_id"], retention=retention)
        if ensure_layout:
            self._ensure_layout(workspace)
        return workspace

    def write_dirty(self, workspace: Workspace, payload: dict[str, str]) -> None:
        atomic_write(
            workspace.staging_root,
            workspace.dirty_path,
            json.dumps(payload, sort_keys=True).encode("utf-8") + b"\n",
        )

    def remove_dirty(self, workspace: Workspace) -> None:
        if workspace.dirty_path.exists():
            workspace.dirty_path.unlink()

    def _ensure_layout(self, workspace: Workspace) -> None:
        if workspace.artifact_root.exists() and not workspace.artifact_root.is_dir():
            raise WorkspaceConfigurationError("Artifact path must be a directory.")
        if workspace.operational_root.exists() and not workspace.operational_root.is_dir():
            raise WorkspaceConfigurationError("Operational path must be a directory.")
        workspace.artifact_root.mkdir(parents=True, exist_ok=True)
        workspace.staging_root.mkdir(parents=True, exist_ok=True)
        workspace.runs_root.mkdir(parents=True, exist_ok=True)
        workspace.locks_root.mkdir(parents=True, exist_ok=True)
        workspace.objects_root.mkdir(parents=True, exist_ok=True)
        (workspace.root / "inbox").mkdir(parents=True, exist_ok=True)
