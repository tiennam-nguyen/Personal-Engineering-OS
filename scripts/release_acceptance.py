"""Black-box clean-install release acceptance using only an installed PEOS executable."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import cast


def command(executable: Path, *arguments: str) -> dict[str, object]:
    completed = subprocess.run(
        [str(executable), *arguments],
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"PEOS command failed ({completed.returncode}): {completed.stderr.strip()}"
        )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("Expected a JSON object from PEOS command.")
    return cast(dict[str, object], value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--peos-exe", type=Path, required=True)
    parser.add_argument("--example-backup", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    arguments = parser.parse_args()
    executable = arguments.peos_exe.resolve()
    backup = arguments.example_backup.resolve()
    fixtures = arguments.fixtures.resolve()
    verified = command(executable, "backup", "verify", str(backup))
    with tempfile.TemporaryDirectory(prefix="peos-release-") as temporary:
        temporary_root = Path(temporary).resolve()
        workspace = temporary_root / "restored"
        restored = command(executable, "backup", "restore", str(backup), "--to", str(workspace))
        if verified["source_generation"] != restored["restored_generation"]:
            raise RuntimeError("Restored generation differs from verified backup.")
        doctor_before = command(executable, "--workspace", str(workspace), "doctor")
        if doctor_before["healthy"] is not True:
            raise RuntimeError("Restored workspace doctor is not healthy.")

        inbox = workspace / "inbox"
        inbox.mkdir(exist_ok=True)
        shutil.copyfile(fixtures / "research/source.txt", inbox / "release-source.txt")
        research = command(
            executable,
            "--workspace",
            str(workspace),
            "research",
            "compile",
            "--question",
            "What does the synthetic release evidence state?",
            "--source",
            "inbox/release-source.txt",
        )
        research_verify = command(
            executable, "--workspace", str(workspace), "run", "verify", str(research["run_id"])
        )

        target = temporary_root / "target"
        shutil.copytree(fixtures / "project/target", target)
        request = json.loads((fixtures / "project/request-template.json").read_text())
        request["repository"] = {
            "mode": "existing_repository",
            "root": str(target),
            "reads": [
                {"path": "pyproject.toml", "role": "manifest", "question": "Toolchain?"},
                {"path": "src/app.py", "role": "entrypoint", "question": "Entrypoint?"},
                {"path": "tests/test_app.py", "role": "test", "question": "Regression?"},
            ],
            "flow_paths": ["src/app.py", "tests/test_app.py"],
            "candidate_change_paths": ["src/app.py", "tests/test_app.py"],
            "forbidden_change_paths": ["README.md"],
        }
        request_path = temporary_root / "project-request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        project = command(
            executable,
            "--workspace",
            str(workspace),
            "project",
            "compile",
            "--request-file",
            str(request_path),
        )
        project_verify = command(
            executable, "--workspace", str(workspace), "run", "verify", str(project["run_id"])
        )

        learning = command(
            executable,
            "--workspace",
            str(workspace),
            "learn",
            "compile",
            "--goal-file",
            str(fixtures / "learning/goal.json"),
            "--diagnostic-file",
            str(fixtures / "learning/diagnostic.json"),
        )
        goal_ref = cast(
            list[dict[str, object]], cast(dict[str, object], learning["outputs"])["artifacts"]
        )[0]
        attempt_path = temporary_root / "attempt.json"
        attempt_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "goal_artifact_id": goal_ref["artifact_id"],
                    "goal_revision": goal_ref["content_hash"],
                    "exercise_id": "exercise-interval-1",
                    "answer": "low through high",
                }
            ),
            encoding="utf-8",
        )
        attempt = command(
            executable,
            "--workspace",
            str(workspace),
            "learn",
            "attempt",
            "--goal",
            str(goal_ref["artifact_id"]),
            "--attempt-file",
            str(attempt_path),
        )
        learning_verify = command(
            executable, "--workspace", str(workspace), "run", "verify", str(learning["run_id"])
        )
        attempt_verify = command(
            executable, "--workspace", str(workspace), "run", "verify", str(attempt["run_id"])
        )
        index_path = workspace / ".peos/index.sqlite3"
        if index_path.resolve() != (workspace / ".peos/index.sqlite3").resolve():
            raise RuntimeError("Unsafe index deletion target.")
        index_path.unlink()
        rebuilt = command(executable, "--workspace", str(workspace), "index", "rebuild")
        doctor_after = command(executable, "--workspace", str(workspace), "doctor")
        if doctor_after["healthy"] is not True:
            raise RuntimeError("Final workspace doctor is not healthy.")
        if not all(
            item.get("valid") is True
            for item in (research_verify, project_verify, learning_verify, attempt_verify)
        ):
            raise RuntimeError("A compiler run failed independent verification.")
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "backup_id": verified["backup_id"],
                    "restored_generation": restored["restored_generation"],
                    "research_run_id": research["run_id"],
                    "project_run_id": project["run_id"],
                    "learning_run_id": learning["run_id"],
                    "attempt_run_id": attempt["run_id"],
                    "artifacts_indexed": rebuilt["artifacts_indexed"],
                    "doctor_before": doctor_before["healthy"],
                    "doctor_after": doctor_after["healthy"],
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
