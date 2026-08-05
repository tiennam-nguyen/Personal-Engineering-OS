"""Versioned protocol identity and immutable definition."""

from __future__ import annotations

import re
from dataclasses import dataclass

from peos.domain.errors import ValidationError

_NAME = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


@dataclass(frozen=True)
class ProtocolDefinition:
    name: str
    version: str
    path: str
    sha256: str
    task_kinds: tuple[str, ...]
    output_contracts: tuple[str, ...]
    sensitivity_ceiling: str
    status: str
    content: str


def validate_protocol_identity(name: str, version: str) -> None:
    if not _NAME.fullmatch(name):
        raise ValidationError("Protocol name is invalid.")
    if not _VERSION.fullmatch(version):
        raise ValidationError("Protocol version is invalid.")


def validate_protocol_definition(protocol: ProtocolDefinition) -> ProtocolDefinition:
    validate_protocol_identity(protocol.name, protocol.version)
    if not protocol.task_kinds or len(set(protocol.task_kinds)) != len(protocol.task_kinds):
        raise ValidationError("Protocol task kinds must be unique and non-empty.")
    if not protocol.output_contracts or len(set(protocol.output_contracts)) != len(
        protocol.output_contracts
    ):
        raise ValidationError("Protocol output contracts must be unique and non-empty.")
    if protocol.status not in {"active", "deprecated", "disabled"}:
        raise ValidationError("Protocol status is invalid.")
    if protocol.sensitivity_ceiling not in {"public", "private", "confidential"}:
        raise ValidationError("Protocol sensitivity ceiling is invalid.")
    if (
        not protocol.content.strip()
        or not protocol.content.endswith("\n")
        or protocol.content.endswith("\n\n")
    ):
        raise ValidationError("Protocol content must be non-empty text with exactly one final LF.")
    return protocol
