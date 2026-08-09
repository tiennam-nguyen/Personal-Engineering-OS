from __future__ import annotations

from pathlib import Path

import pytest

from peos.adapters.filesystem.project_estate_reader import FilesystemProjectEstateReader
from peos.domain.errors import ProjectEstatePathError


def test_reader_is_bounded_and_tree_does_not_read_bodies(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_bytes(b"hello\n")
    reader = FilesystemProjectEstateReader(root)
    assert reader.read("src/app.py") == b"hello\n"
    assert reader.tree() == ("src/", "src/app.py")
    with pytest.raises(ProjectEstatePathError):
        reader.read("../outside")
