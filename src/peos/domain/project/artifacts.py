"""Strict payload validation for the three Milestone 5 artifact types."""

from __future__ import annotations

from peos.domain.errors import ValidationError

_KEYS = {
    "project.map": {
        "schema_version",
        "project_slug",
        "repository",
        "tree",
        "reads",
        "flow_paths",
        "layers",
        "accepted_result",
        "previous_map_ref",
    },
    "project.charter": {
        "schema_version",
        "project_slug",
        "objective",
        "requirements",
        "architecture",
        "walking_skeleton",
        "map_ref",
        "request_ref",
        "research_context_ref",
    },
    "project.codex_packet": {
        "schema_version",
        "packet_format_version",
        "project_slug",
        "map_ref",
        "charter_ref",
        "request_hash",
        "research_context_ref",
        "input_files",
        "allowed_paths",
        "forbidden_paths",
        "verification",
    },
    "project.adr": {
        "schema_version",
        "decision_key",
        "context",
        "decision",
        "alternatives",
        "consequences",
        "falsifier",
        "project_charter_ref",
        "supporting_claim_refs",
    },
}


def validate_project_payload(type_: str, payload: object, body: str) -> None:
    if (
        not isinstance(payload, dict)
        or set(payload) != _KEYS[type_]
        or payload.get("schema_version") != 1
    ):
        raise ValidationError("Project artifact payload fields are invalid.")
    if type_ == "project.map":
        reads = payload["reads"]
        layers = payload["layers"]
        if (
            not isinstance(reads, list)
            or not reads
            or not isinstance(layers, dict)
            or set(layers) != {"l0", "l1", "l2", "l3", "unknowns"}
        ):
            raise ValidationError("Project map payload is invalid.")
        for item in reads:
            if (
                not isinstance(item, dict)
                or set(item)
                != {
                    "path",
                    "role",
                    "question",
                    "raw_hash",
                    "object_hash",
                    "byte_count",
                    "evidence_grade",
                }
                or item["evidence_grade"] != "READ"
            ):
                raise ValidationError("Project map read evidence is invalid.")
    elif type_ == "project.charter":
        objective, requirements, architecture, skeleton = (
            payload["objective"],
            payload["requirements"],
            payload["architecture"],
            payload["walking_skeleton"],
        )
        if not isinstance(objective, dict) or set(objective) != {
            "mission",
            "stakeholder",
            "optimized_attributes",
            "deliberate_sacrifices",
            "non_negotiables",
            "assumptions",
            "scope_exclusions",
        }:
            raise ValidationError("Project objective is invalid.")
        if not 1 <= len(objective["optimized_attributes"]) <= 3 or not objective["non_negotiables"]:
            raise ValidationError("Project objective constraints are invalid.")
        if (
            not isinstance(requirements, list)
            or not requirements
            or any(
                item.get("priority") == "must" and item.get("acceptance") is None
                for item in requirements
                if isinstance(item, dict)
            )
        ):
            raise ValidationError("Project requirements are invalid.")
        if not isinstance(architecture, dict) or set(architecture) != {
            "main_design",
            "pre_mortem",
            "orthogonal",
            "shadow_review",
            "door_decisions",
            "trade_ledger",
            "recommendation",
            "falsifier",
            "repository_claims",
        }:
            raise ValidationError("Project architecture is invalid.")
        if any(
            item.get("classification") == "one_way"
            and item.get("treatment_kind") not in {"spike", "seam", "explicit_acceptance"}
            for item in architecture["door_decisions"]
            if isinstance(item, dict)
        ):
            raise ValidationError("One-way project decisions require treatment.")
        if not isinstance(skeleton, dict) or set(skeleton) != {
            "key",
            "objective",
            "scope",
            "allowed_paths",
            "forbidden_paths",
            "deliverables",
            "definition_of_done",
            "verification",
            "rollback_recovery",
            "risks",
            "assumptions",
        }:
            raise ValidationError("Walking skeleton is invalid.")
    elif type_ == "project.codex_packet":
        if payload["packet_format_version"] != "1.0.0" or not body.startswith(
            "# Codex Milestone Packet\n"
        ):
            raise ValidationError("Codex packet body or format is invalid.")
    else:
        required = ("decision_key", "context", "decision", "falsifier")
        if any(not isinstance(payload[key], str) or not payload[key].strip() for key in required):
            raise ValidationError("Project ADR text fields are invalid.")
        if not isinstance(payload["alternatives"], list) or not payload["alternatives"]:
            raise ValidationError("Project ADR alternatives are required.")
        if not isinstance(payload["consequences"], list) or not payload["consequences"]:
            raise ValidationError("Project ADR consequences are required.")
        if (
            not isinstance(payload["supporting_claim_refs"], list)
            or not payload["supporting_claim_refs"]
        ):
            raise ValidationError("Project ADR supporting claims are required.")
        references = [payload["project_charter_ref"], *payload["supporting_claim_refs"]]
        if any(
            not isinstance(reference, dict)
            or set(reference) != {"artifact_id", "revision"}
            or not isinstance(reference["artifact_id"], str)
            or not isinstance(reference["revision"], str)
            for reference in references
        ):
            raise ValidationError("Project ADR exact references are invalid.")


def project_id(run_id: str, type_: str, ordinal: int) -> str:
    import hashlib

    return (
        "art_"
        + hashlib.sha256(f"{run_id}:project.compile:1.0.0:{type_}:{ordinal}".encode()).hexdigest()[
            :32
        ]
    )
