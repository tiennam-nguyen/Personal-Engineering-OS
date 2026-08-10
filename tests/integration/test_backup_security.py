from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from peos.adapters.filesystem.hardening import verify_backup
from peos.cli.main import main
from peos.domain.errors import HardeningIntegrityError
from tests.integration.test_backup_restore import populated


@pytest.mark.parametrize("unsafe", ["/absolute", "C:/absolute", "..\\escape", "a/../b"])
def test_backup_rejects_unsafe_manifest_paths(tmp_path: Path, unsafe: str) -> None:
    _, repository = populated(tmp_path)
    backup = tmp_path / "backup"
    repository.create_backup(backup, False)
    manifest = json.loads((backup / "manifest.json").read_text())
    manifest["files"][0]["path"] = unsafe
    (backup / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(HardeningIntegrityError):
        verify_backup(backup)


@pytest.mark.skipif(os.name == "nt", reason="Creating symlinks may require Windows privilege")
def test_backup_rejects_payload_symlink(tmp_path: Path) -> None:
    _, repository = populated(tmp_path)
    backup = tmp_path / "backup"
    repository.create_backup(backup, False)
    manifest = json.loads((backup / "manifest.json").read_text())
    target = backup / "payload" / manifest["files"][0]["path"]
    target.unlink()
    target.symlink_to(backup / "manifest.json")
    with pytest.raises(HardeningIntegrityError):
        verify_backup(backup)


def test_expected_backup_cli_error_has_no_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["backup", "verify", str(tmp_path / "missing")])
    captured = capsys.readouterr()
    assert code != 0
    assert "Traceback" not in captured.err
    assert captured.out == ""
