"""Strict workspace-owned protocol registry loader."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from peos.domain.errors import (
    ProtocolIntegrityError,
    ProtocolNotFound,
    ProtocolRegistryError,
    ProtocolRegistryNotFound,
)
from peos.domain.protocols.model import (
    ProtocolDefinition,
    validate_protocol_definition,
    validate_protocol_identity,
)


class FilesystemProtocolRepository:
    def __init__(self, root: Path) -> None:
        self._root = root

    def list(self) -> list[ProtocolDefinition]:
        registry = self._root / "protocols" / "registry.yaml"
        if not registry.exists():
            raise ProtocolRegistryNotFound("Protocol registry was not found.")
        try:
            data = yaml.safe_load(registry.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise ProtocolRegistryError("Protocol registry cannot be read.") from error
        if (
            not isinstance(data, dict)
            or set(data) != {"schema_version", "protocols"}
            or data["schema_version"] != 1
            or not isinstance(data["protocols"], list)
        ):
            raise ProtocolRegistryError("Protocol registry schema is invalid.")
        protocols = [self._record(record) for record in data["protocols"]]
        keys = [(p.name, p.version) for p in protocols]
        if len(keys) != len(set(keys)):
            raise ProtocolRegistryError("Protocol registry contains duplicate versions.")
        return sorted(
            protocols, key=lambda p: (p.name, tuple(int(x) for x in p.version.split(".")))
        )

    def get(self, name: str, version: str) -> ProtocolDefinition:
        validate_protocol_identity(name, version)
        for protocol in self.list():
            if protocol.name == name and protocol.version == version:
                return protocol
        raise ProtocolNotFound("Protocol version was not found.")

    def _record(self, record: object) -> ProtocolDefinition:
        fields = {
            "name",
            "version",
            "path",
            "sha256",
            "task_kinds",
            "output_contracts",
            "sensitivity_ceiling",
            "status",
        }
        if not isinstance(record, dict) or set(record) != fields:
            raise ProtocolRegistryError("Protocol record fields are invalid.")
        name, version = record["name"], record["version"]
        if not isinstance(name, str) or not isinstance(version, str):
            raise ProtocolRegistryError("Protocol identity is invalid.")
        expected = f"protocols/{name}/{version}.md"
        path = record["path"]
        if path != expected:
            raise ProtocolRegistryError("Protocol path is invalid.")
        target = (self._root / Path(path)).resolve()
        protocols = (self._root / "protocols").resolve()
        if protocols not in target.parents or not target.exists() or target.is_symlink():
            raise ProtocolRegistryError("Protocol path escapes workspace protocols.")
        try:
            raw = target.read_bytes()
            content = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise ProtocolRegistryError("Protocol content cannot be read.") from error
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        if record["sha256"] != digest:
            raise ProtocolIntegrityError("Protocol raw-byte hash does not match registry.")
        try:
            protocol = ProtocolDefinition(
                name,
                version,
                path,
                digest,
                tuple(record["task_kinds"]),
                tuple(record["output_contracts"]),
                record["sensitivity_ceiling"],
                record["status"],
                content,
            )
        except TypeError as error:
            raise ProtocolRegistryError("Protocol record values are invalid.") from error
        return validate_protocol_definition(protocol)
