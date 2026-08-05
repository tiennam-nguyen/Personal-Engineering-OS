"""Architecture guard for the dependency rules established by Milestone 0."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).parents[2] / "src" / "peos"


@pytest.mark.parametrize(
    ("package", "forbidden"),
    [
        ("domain", ("peos.adapters", "peos.cli", "sqlite3", "pathlib", "os", "openai")),
        ("application", ("peos.adapters", "peos.cli")),
        ("workflows", ("peos.adapters",)),
        ("cli", ("peos.adapters",)),
    ],
)
def test_dependency_direction(package: str, forbidden: tuple[str, ...]) -> None:
    package_root = SOURCE_ROOT / package
    for path in package_root.rglob("*.py") if package_root.exists() else ():
        imported_modules = _imported_modules(path)
        for imported_module in imported_modules:
            assert not imported_module.startswith(forbidden), (
                f"{path.relative_to(SOURCE_ROOT)} imports forbidden module {imported_module!r}"
            )


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
