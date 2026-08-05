from __future__ import annotations

from typing import Protocol

from peos.domain.protocols.model import ProtocolDefinition


class ProtocolRepository(Protocol):
    def list(self) -> list[ProtocolDefinition]: ...
    def get(self, name: str, version: str) -> ProtocolDefinition: ...
