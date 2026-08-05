from __future__ import annotations

from typing import Protocol

from peos.domain.models.request import ModelRequest
from peos.domain.models.response import ModelResponse


class ModelGateway(Protocol):
    provider: str
    model: str
    model_revision: str
    capabilities: frozenset[str]
    sensitivity_ceiling: str

    def generate(self, request: ModelRequest) -> ModelResponse: ...
