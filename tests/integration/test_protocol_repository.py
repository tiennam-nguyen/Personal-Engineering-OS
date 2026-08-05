import hashlib
from pathlib import Path

import pytest

from peos.adapters.filesystem.protocol_repository import FilesystemProtocolRepository
from peos.domain.errors import ProtocolIntegrityError, ProtocolRegistryError


def make(
    root: Path,
    *,
    digest: str | None = None,
    path: str = "protocols/sample.concept-summary/1.0.0.md",
) -> FilesystemProtocolRepository:
    content = "# Protocol\n"
    target = root / "protocols" / "sample.concept-summary" / "1.0.0.md"
    target.parent.mkdir(parents=True)
    target.write_text(content, encoding="utf-8", newline="")
    actual = "sha256:" + hashlib.sha256(content.encode()).hexdigest()
    (root / "protocols" / "registry.yaml").write_text(
        f"""schema_version: 1
protocols:
  - name: sample.concept-summary
    version: 1.0.0
    path: {path}
    sha256: {digest or actual}
    task_kinds: [summarization]
    output_contracts: [sample.concept_summary.v1]
    sensitivity_ceiling: private
    status: active
""",
        encoding="utf-8",
        newline="",
    )
    return FilesystemProtocolRepository(root)


def test_valid_load_and_deterministic_list(tmp_path: Path) -> None:
    repository = make(tmp_path)
    assert repository.list() == repository.list()
    assert repository.get("sample.concept-summary", "1.0.0").content == "# Protocol\n"


def test_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ProtocolIntegrityError):
        make(tmp_path, digest="sha256:" + "0" * 64).list()


def test_noncanonical_path_and_unknown_keys_fail(tmp_path: Path) -> None:
    with pytest.raises(ProtocolRegistryError):
        make(tmp_path, path="../outside.md").list()
