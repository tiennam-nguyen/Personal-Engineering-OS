"""Bounded target-repository read contract."""

from typing import Protocol


class ProjectEstateReader(Protocol):
    def tree(self) -> tuple[str, ...]: ...
    def read(self, relative_path: str) -> bytes: ...
