"""Storage-neutral release-hardening values and deterministic fingerprints."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass

from peos.domain.errors import HardeningIntegrityError

HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")


@dataclass(frozen=True)
class InventoryEntry:
    relative_path: str
    classification: str
    byte_size: int
    sha256: str

    def __post_init__(self) -> None:
        validate_relative_path(self.relative_path)
        if not self.classification or self.byte_size < 0 or not HASH_PATTERN.fullmatch(self.sha256):
            raise HardeningIntegrityError("Workspace inventory entry is invalid.")


@dataclass(frozen=True)
class WorkspaceInventory:
    workspace_id: str
    entries: tuple[InventoryEntry, ...]
    generation: str


@dataclass(frozen=True)
class RetentionPolicy:
    raw_model_payload_days: int = 3650
    cache_days: int = 30
    keep_failed_run_evidence: bool = True
    quarantine_days: int = 30

    def __post_init__(self) -> None:
        if self.raw_model_payload_days < 0 or self.cache_days < 0 or self.quarantine_days < 1:
            raise HardeningIntegrityError("Retention policy is invalid.")


def validate_relative_path(value: str) -> str:
    if not value or "\\" in value:
        raise HardeningIntegrityError("Path must use normalized relative separators.")
    parts = value.split("/")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value) or ".." in parts:
        raise HardeningIntegrityError("Path must remain relative and traversal-free.")
    if any(part in {"", "."} for part in parts):
        raise HardeningIntegrityError("Path is not normalized.")
    return value


def sha256_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def inventory_generation(entries: tuple[InventoryEntry, ...]) -> str:
    ordered = sorted(entries, key=lambda item: item.relative_path)
    if len({item.relative_path.casefold() for item in ordered}) != len(ordered):
        raise HardeningIntegrityError("Workspace inventory contains duplicate normalized paths.")
    payload = [
        {
            "path": item.relative_path,
            "classification": item.classification,
            "sha256": item.sha256,
        }
        for item in ordered
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(encoded)


def entry_mapping(entry: InventoryEntry) -> dict[str, object]:
    value = asdict(entry)
    value["path"] = value.pop("relative_path")
    value["size_bytes"] = value.pop("byte_size")
    return value
