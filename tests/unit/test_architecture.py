"""Architecture guard for the dependency rules established by Milestone 0."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).parents[2] / "src" / "peos"


@pytest.mark.parametrize(
    ("package", "forbidden"),
    [
        (
            "domain",
            (
                "peos.adapters",
                "peos.cli",
                "sqlite3",
                "pathlib",
                "os",
                "yaml",
                "argparse",
                "openai",
            ),
        ),
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


def test_filesystem_run_repository_implements_port_shape() -> None:
    from peos.adapters.filesystem.run_repository import FilesystemRunRepository

    required = {
        "create",
        "read_manifest",
        "read_inputs",
        "events",
        "append",
        "write_evidence",
        "read_evidence",
        "write_outputs",
        "read_outputs",
    }
    assert required <= set(dir(FilesystemRunRepository))


def test_registered_workflow_has_independent_verifier() -> None:
    from peos.workflows import sample

    assert callable(sample.prepare)
    assert callable(sample.verify_prepared)


def test_no_tool_or_milestone_5_modules_exist() -> None:
    forbidden = ("tool_executor", "project_compiler")
    paths = [path.as_posix() for path in SOURCE_ROOT.rglob("*.py")]
    assert not any(name in path for name in forbidden for path in paths)


def test_source_object_store_implements_port_shape() -> None:
    from peos.adapters.filesystem.source_object_store import FilesystemSourceObjectStore

    assert {"put", "read", "verify", "exists", "locator"} <= set(dir(FilesystemSourceObjectStore))
