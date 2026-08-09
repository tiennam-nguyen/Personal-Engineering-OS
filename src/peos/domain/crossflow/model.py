"""Strict Cross-Workflow Graph request parsing."""

from __future__ import annotations

from typing import Any, cast

from peos.domain.artifacts.validation import CONTENT_HASH_PATTERN, validate_artifact_id
from peos.domain.errors import CrossflowInputInvalid

KINDS = frozenset(
    {
        "project_failure_to_learning_exercise",
        "research_claim_to_project_adr",
        "learning_gap_to_research_question",
    }
)


def parse_request(value: object) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or value.get("kind") not in KINDS
    ):
        raise CrossflowInputInvalid("Crossflow request envelope is invalid.")
    kind = value["kind"]
    expected = {
        "project_failure_to_learning_exercise": {
            "schema_version",
            "kind",
            "project_packet_id",
            "project_packet_revision",
            "failure",
            "learning_target",
        },
        "research_claim_to_project_adr": {
            "schema_version",
            "kind",
            "research_claim_id",
            "research_claim_revision",
            "project_charter_id",
            "project_charter_revision",
            "adr",
        },
        "learning_gap_to_research_question": {
            "schema_version",
            "kind",
            "learning_goal_id",
            "learning_goal_revision",
            "gap_concept_id",
        },
    }[kind]
    if set(value) != expected:
        raise CrossflowInputInvalid("Crossflow request fields are invalid.")
    result = cast(dict[str, Any], value)
    id_keys = [
        key
        for key in value
        if key
        in {
            "project_packet_id",
            "research_claim_id",
            "project_charter_id",
            "learning_goal_id",
        }
    ]
    revision_keys = [key for key in value if key.endswith("_revision")]
    try:
        for key in id_keys:
            validate_artifact_id(value[key])
        if any(
            not isinstance(value[key], str) or not CONTENT_HASH_PATTERN.fullmatch(value[key])
            for key in revision_keys
        ):
            raise CrossflowInputInvalid("Crossflow source revision is invalid.")
    except (TypeError, CrossflowInputInvalid) as error:
        if isinstance(error, CrossflowInputInvalid):
            raise
        raise CrossflowInputInvalid("Crossflow source reference is invalid.") from error
    if kind == "project_failure_to_learning_exercise":
        _strict_object(
            result["failure"],
            {
                "verification_cwd",
                "verification_argv",
                "expected_exit_code",
                "reported_exit_code",
                "failed_check",
                "expected_behavior",
                "observed_behavior",
                "reported_by",
            },
        )
        _strict_object(
            result["learning_target"], {"concept_id", "concept_title", "estimated_minutes"}
        )
        failure, target = result["failure"], result["learning_target"]
        if failure["reported_by"] not in {"user", "external_tool"} or any(
            not isinstance(failure[key], str) or not failure[key].strip()
            for key in (
                "verification_cwd",
                "failed_check",
                "expected_behavior",
                "observed_behavior",
            )
        ):
            raise CrossflowInputInvalid("Project failure report is invalid.")
        if (
            not isinstance(failure["verification_argv"], list)
            or not failure["verification_argv"]
            or not all(isinstance(item, str) and item for item in failure["verification_argv"])
        ):
            raise CrossflowInputInvalid("Project failure argv is invalid.")
        if not all(
            isinstance(failure[key], int) and not isinstance(failure[key], bool)
            for key in ("expected_exit_code", "reported_exit_code")
        ):
            raise CrossflowInputInvalid("Project failure exit codes are invalid.")
        if (
            any(
                not isinstance(target[key], str) or not target[key].strip()
                for key in ("concept_id", "concept_title")
            )
            or not isinstance(target["estimated_minutes"], int)
            or target["estimated_minutes"] <= 0
        ):
            raise CrossflowInputInvalid("Learning target is invalid.")
    elif kind == "research_claim_to_project_adr":
        _strict_object(
            result["adr"],
            {"decision_key", "context", "decision", "alternatives", "consequences", "falsifier"},
        )
        adr = result["adr"]
        if any(
            not isinstance(adr[key], str) or not adr[key].strip()
            for key in ("decision_key", "context", "decision", "falsifier")
        ) or any(
            not isinstance(adr[key], list)
            or not adr[key]
            or not all(isinstance(item, str) and item.strip() for item in adr[key])
            for key in ("alternatives", "consequences")
        ):
            raise CrossflowInputInvalid("ADR request is invalid.")
    elif not isinstance(result["gap_concept_id"], str) or not result["gap_concept_id"].strip():
        raise CrossflowInputInvalid("Learning gap concept ID is invalid.")
    return result


def _strict_object(value: object, keys: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise CrossflowInputInvalid("Crossflow nested request fields are invalid.")
