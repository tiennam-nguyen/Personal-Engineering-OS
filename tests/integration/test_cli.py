from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(workspace: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "peos.cli.main", "--workspace", str(workspace), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def test_cli_round_trip_and_rebuild(tmp_path: Path) -> None:
    initialized = _run(tmp_path, "init")
    assert initialized.returncode == 0
    assert json.loads(initialized.stdout)["status"] == "initialized"
    created = _run(tmp_path, "artifact", "create", "--title", "Title", "--body", "Body text")
    artifact_id = json.loads(created.stdout)["id"]
    assert _run(tmp_path, "artifact", "get", artifact_id).returncode == 0
    assert json.loads(_run(tmp_path, "artifact", "search", "body").stdout)[0]["id"] == artifact_id
    assert json.loads(_run(tmp_path, "artifact", "verify", artifact_id).stdout)["valid"] is True
    (tmp_path / ".peos" / "index.sqlite3").unlink()
    assert json.loads(_run(tmp_path, "index", "rebuild").stdout)["status"] == "rebuilt"


def test_cli_expected_errors_are_safe(tmp_path: Path) -> None:
    _run(tmp_path, "init")
    invalid = _run(tmp_path, "artifact", "create", "--title", "", "--body", "Body")
    assert invalid.returncode == 2
    assert "Traceback" not in invalid.stderr
    missing = _run(tmp_path, "artifact", "get", "art_" + "0" * 32)
    assert missing.returncode == 3
    assert "Traceback" not in missing.stderr
