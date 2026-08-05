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
from peos.domain.errors import WorkspaceConfigurationError, WorkspaceNotFound


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Workspace:
    root: Path
    workspace_id: str

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
        }
        encoded = yaml.safe_dump(
            config, sort_keys=False, allow_unicode=True, default_flow_style=False
        ).encode("utf-8")
        atomic_write(workspace.staging_root, config_path, encoded)
        return workspace, True

    def open(self, root: Path) -> Workspace:
        root = root.resolve()
        config_path = root / "peos.yaml"
        if not config_path.exists():
            raise WorkspaceNotFound("Workspace configuration peos.yaml was not found.")
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise WorkspaceConfigurationError("Workspace configuration cannot be read.") from error
        if not isinstance(data, dict) or set(data) != {
            "schema_version",
            "workspace_id",
            "created_at",
        }:
            raise WorkspaceConfigurationError("Workspace configuration is incompatible.")
        if data["schema_version"] != 1 or not isinstance(data["workspace_id"], str):
            raise WorkspaceConfigurationError("Workspace configuration is incompatible.")
        try:
            validate_workspace_id(data["workspace_id"])
            datetime.fromisoformat(str(data["created_at"]).replace("Z", "+00:00"))
        except (ValueError, WorkspaceConfigurationError) as error:
            raise WorkspaceConfigurationError("Workspace configuration is invalid.") from error
        workspace = Workspace(root=root, workspace_id=data["workspace_id"])
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
