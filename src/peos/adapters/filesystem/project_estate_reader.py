"""Filesystem implementation of bounded project-estate reads."""

from __future__ import annotations

from pathlib import Path

from peos.domain.errors import ProjectEstatePathError
from peos.domain.project.model import normalized_relative_path


class FilesystemProjectEstateReader:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve(strict=True)
        if not self._root.is_dir():
            raise ProjectEstatePathError("Target repository root is not a directory.")

    def _path(self, relative_path: str) -> Path:
        try:
            normalized = normalized_relative_path(relative_path)
        except Exception as error:
            raise ProjectEstatePathError("Target repository path is invalid.") from error
        path = (self._root / normalized).resolve(strict=True)
        if self._root not in path.parents:
            raise ProjectEstatePathError("Target repository path escapes the repository root.")
        return path

    def read(self, relative_path: str) -> bytes:
        path = self._path(relative_path)
        if not path.is_file():
            raise ProjectEstatePathError("Target repository read path is not a file.")
        try:
            return path.read_bytes()
        except OSError as error:
            raise ProjectEstatePathError("Target repository file cannot be read.") from error

    def tree(self) -> tuple[str, ...]:
        entries: list[str] = []
        for first in sorted(self._root.iterdir(), key=lambda item: item.name):
            entries.append(
                first.relative_to(self._root).as_posix() + ("/" if first.is_dir() else "")
            )
            if first.is_dir() and not first.is_symlink():
                for second in sorted(first.iterdir(), key=lambda item: item.name):
                    entries.append(
                        second.relative_to(self._root).as_posix() + ("/" if second.is_dir() else "")
                    )
        return tuple(entries)
