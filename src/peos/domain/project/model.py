"""Strict immutable values and validation for Project Compiler inputs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from peos.domain.errors import ProjectRequestInvalid

_REQUEST_KEYS = {
    "schema_version",
    "project_slug",
    "request",
    "stakeholder",
    "intolerable_failure",
    "constraints",
    "definition_of_done",
    "deadline",
    "repository",
    "verification",
    "research_synthesis_id",
    "sensitivity",
}
_REPOSITORY_KEYS = {
    "mode",
    "root",
    "reads",
    "flow_paths",
    "candidate_change_paths",
    "forbidden_change_paths",
}
_READ_KEYS = {"path", "role", "question"}
_VERIFY_KEYS = {"cwd", "argv", "expected_exit_code", "expected_evidence"}
_ROLES = {"manifest", "config", "entrypoint", "flow", "test", "other"}


def normalized_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or "\\" in value:
        raise ProjectRequestInvalid("Project paths must be non-empty POSIX relative paths.")
    parts = value.split("/")
    if value.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise ProjectRequestInvalid("Project path escapes or is not normalized.")
    if ":" in parts[0]:
        raise ProjectRequestInvalid("Project path must be relative.")
    return "/".join(parts)


@dataclass(frozen=True)
class ProjectReadSpec:
    path: str
    role: str
    question: str


@dataclass(frozen=True)
class VerificationContract:
    cwd: str
    argv: tuple[str, ...]
    expected_exit_code: int
    expected_evidence: str


@dataclass(frozen=True)
class ProjectRequest:
    schema_version: int
    project_slug: str
    request: str
    stakeholder: str
    intolerable_failure: str
    constraints: tuple[str, ...]
    definition_of_done: str
    deadline: str | None
    repository_root: str
    reads: tuple[ProjectReadSpec, ...]
    flow_paths: tuple[str, ...]
    candidate_change_paths: tuple[str, ...]
    forbidden_change_paths: tuple[str, ...]
    verification: VerificationContract
    research_synthesis_id: str | None
    sensitivity: str


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProjectRequestInvalid(f"{name} must be non-empty text.")
    return value.strip()


def _strings(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ProjectRequestInvalid(f"{name} must be an array of non-empty strings.")
    return tuple(item.strip() for item in value)


def parse_project_request(value: object) -> ProjectRequest:
    if not isinstance(value, dict) or set(value) != _REQUEST_KEYS:
        raise ProjectRequestInvalid("Project request fields are invalid.")
    repository = value["repository"]
    verification = value["verification"]
    if not isinstance(repository, dict) or set(repository) != _REPOSITORY_KEYS:
        raise ProjectRequestInvalid("Project repository fields are invalid.")
    if repository["mode"] != "existing_repository":
        raise ProjectRequestInvalid("Only existing_repository mode is supported.")
    if not isinstance(verification, dict) or set(verification) != _VERIFY_KEYS:
        raise ProjectRequestInvalid("Project verification fields are invalid.")
    if value["schema_version"] != 1 or not re.fullmatch(
        r"[a-z0-9]+(?:-[a-z0-9]+)*", str(value["project_slug"])
    ):
        raise ProjectRequestInvalid("Project request schema or slug is invalid.")
    raw_reads = repository["reads"]
    if not isinstance(raw_reads, list) or not raw_reads:
        raise ProjectRequestInvalid("Project read set must be non-empty.")
    reads: list[ProjectReadSpec] = []
    for item in raw_reads:
        if not isinstance(item, dict) or set(item) != _READ_KEYS:
            raise ProjectRequestInvalid("Project read fields are invalid.")
        role = str(item["role"])
        if role not in _ROLES:
            raise ProjectRequestInvalid("Project read role is invalid.")
        reads.append(
            ProjectReadSpec(
                normalized_relative_path(item["path"]), role, _text(item["question"], "question")
            )
        )
    read_paths = tuple(item.path for item in reads)
    if len(read_paths) != len(set(read_paths)):
        raise ProjectRequestInvalid("Duplicate project read paths are invalid.")
    flow = tuple(
        normalized_relative_path(item) for item in _strings(repository["flow_paths"], "flow_paths")
    )
    if any(item not in read_paths for item in flow):
        raise ProjectRequestInvalid("Every flow path must be in the explicit read set.")
    candidates = tuple(
        normalized_relative_path(item)
        for item in _strings(repository["candidate_change_paths"], "candidate_change_paths")
    )
    forbidden = tuple(
        normalized_relative_path(item)
        for item in _strings(repository["forbidden_change_paths"], "forbidden_change_paths")
    )
    if (
        len(candidates) != len(set(candidates))
        or len(forbidden) != len(set(forbidden))
        or set(candidates) & set(forbidden)
    ):
        raise ProjectRequestInvalid("Project change scope is duplicate or contradictory.")
    argv = _strings(verification["argv"], "verification.argv")
    if not argv or verification["expected_exit_code"] != 0:
        raise ProjectRequestInvalid("Project verification contract is invalid.")
    deadline = value["deadline"]
    if deadline is not None:
        deadline = _text(deadline, "deadline")
    synthesis = value["research_synthesis_id"]
    if synthesis is not None and not re.fullmatch(r"art_[0-9a-f]{32}", str(synthesis)):
        raise ProjectRequestInvalid("Research synthesis ID is invalid.")
    if value["sensitivity"] not in {"public", "private"}:
        raise ProjectRequestInvalid("Project sensitivity is unsupported.")
    return ProjectRequest(
        1,
        str(value["project_slug"]),
        _text(value["request"], "request"),
        _text(value["stakeholder"], "stakeholder"),
        _text(value["intolerable_failure"], "intolerable_failure"),
        _strings(value["constraints"], "constraints"),
        _text(value["definition_of_done"], "definition_of_done"),
        deadline,
        _text(repository["root"], "repository.root"),
        tuple(reads),
        flow,
        candidates,
        forbidden,
        VerificationContract(
            _text(verification["cwd"], "verification.cwd"),
            argv,
            0,
            _text(verification["expected_evidence"], "expected_evidence"),
        ),
        synthesis,
        str(value["sensitivity"]),
    )
