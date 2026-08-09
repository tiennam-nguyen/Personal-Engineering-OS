"""Strict Codex-result manifest and scope validation."""

from __future__ import annotations

from dataclasses import dataclass

from peos.domain.errors import ProjectResultConflict, ProjectScopeViolation
from peos.domain.project.model import normalized_relative_path


@dataclass(frozen=True)
class ChangedFile:
    path: str
    sha256: str


@dataclass(frozen=True)
class ResultManifest:
    packet_artifact_id: str
    packet_revision: str
    current_map_artifact_id: str
    current_map_revision: str
    changed_files: tuple[ChangedFile, ...]
    verification: dict[str, object]


def parse_result_manifest(value: object) -> ResultManifest:
    keys = {
        "schema_version",
        "packet_artifact_id",
        "packet_revision",
        "current_map_artifact_id",
        "current_map_revision",
        "changed_files",
        "verification",
    }
    verify_keys = {"cwd", "argv", "exit_code", "stdout_sha256", "stderr_sha256", "reported_by"}
    if not isinstance(value, dict) or set(value) != keys or value["schema_version"] != 1:
        raise ProjectResultConflict("Project result manifest fields are invalid.")
    verification = value["verification"]
    if (
        not isinstance(verification, dict)
        or set(verification) != verify_keys
        or verification["reported_by"] not in {"codex", "human", "other"}
    ):
        raise ProjectResultConflict("Project result verification fields are invalid.")
    raw = value["changed_files"]
    if not isinstance(raw, list) or not raw:
        raise ProjectResultConflict("Project result must contain changed files.")
    changed: list[ChangedFile] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ProjectResultConflict("Changed-file fields are invalid.")
        changed.append(ChangedFile(normalized_relative_path(item["path"]), str(item["sha256"])))
    paths = [item.path for item in changed]
    if len(paths) != len(set(paths)):
        raise ProjectScopeViolation("Duplicate changed paths are invalid.")
    return ResultManifest(
        str(value["packet_artifact_id"]),
        str(value["packet_revision"]),
        str(value["current_map_artifact_id"]),
        str(value["current_map_revision"]),
        tuple(changed),
        dict(verification),
    )


def validate_result_scope(result: ResultManifest, packet: dict[str, object]) -> None:
    raw_allowed = packet["allowed_paths"]
    raw_forbidden = packet["forbidden_paths"]
    if not isinstance(raw_allowed, list) or not isinstance(raw_forbidden, list):
        raise ProjectResultConflict("Packet scope is invalid.")
    allowed = set(raw_allowed)
    forbidden = set(raw_forbidden)
    for changed in result.changed_files:
        if changed.path not in allowed or changed.path in forbidden:
            raise ProjectScopeViolation("Changed path is outside packet authority.")
    expected = packet["verification"]
    if (
        not isinstance(expected, dict)
        or result.verification["cwd"] != expected["cwd"]
        or result.verification["argv"] != expected["argv"]
    ):
        raise ProjectResultConflict("Reported verification does not match packet authority.")
    if result.verification["exit_code"] != expected["expected_exit_code"]:
        raise ProjectResultConflict("Reported verification exit code is not acceptable.")
