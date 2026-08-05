"""Derived workspace-local model cache contract."""

from __future__ import annotations

from typing import Protocol


class ModelCache(Protocol):
    def get(self, key: str) -> dict[str, object] | None: ...

    def put(self, key: str, value: dict[str, object]) -> None: ...

    def locator(self, key: str) -> str: ...
