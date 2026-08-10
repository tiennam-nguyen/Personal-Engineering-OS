"""Generate the committed synthetic release backup through production backup code."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tempfile
from pathlib import Path

from peos.adapters.filesystem.hardening import FilesystemHardeningRepository
from peos.adapters.filesystem.source_object_store import FilesystemSourceObjectStore
from peos.adapters.filesystem.workspace import WorkspaceStore
from peos.bootstrap import initialize_workspace
from tests.evaluation_support import qualify_claim_extraction, qualify_project_planning
from tests.project_support import PROTOCOL as PROJECT_PROTOCOL
from tests.research_support import PROTOCOL as RESEARCH_PROTOCOL

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists():
        raise RuntimeError("Release example output already exists.")
    with tempfile.TemporaryDirectory(prefix="peos-example-source-") as temporary:
        root = Path(temporary) / "workspace"
        initialize_workspace(root)
        shutil.copy2(REPOSITORY_ROOT / "MAP.md", root / "MAP.md")
        shutil.copy2(REPOSITORY_ROOT / "PLAN.md", root / "PLAN.md")
        shutil.copytree(REPOSITORY_ROOT / "adr", root / "adr")
        protocols = (
            (
                "research.claim-extraction",
                "claim_extraction",
                "research.candidate_claim_set.v1",
                RESEARCH_PROTOCOL,
            ),
            (
                "project.plan-compilation",
                "project_planning",
                "project.charter_draft.v1",
                PROJECT_PROTOCOL,
            ),
        )
        entries: list[str] = []
        for name, task, contract, raw in protocols:
            path = root / "protocols" / name / "1.0.0.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(raw, encoding="utf-8", newline="")
            entries.append(
                f"  - name: {name}\n    version: 1.0.0\n"
                f"    path: protocols/{name}/1.0.0.md\n    sha256: {digest(raw)}\n"
                f"    task_kinds: [{task}]\n    output_contracts: [{contract}]\n"
                "    sensitivity_ceiling: private\n    status: active\n"
            )
        (root / "protocols" / "registry.yaml").write_text(
            "schema_version: 1\nprotocols:\n" + "".join(entries),
            encoding="utf-8",
            newline="",
        )
        research = qualify_claim_extraction(root, digest(RESEARCH_PROTOCOL))
        project = qualify_project_planning(root, digest(PROJECT_PROTOCOL))
        if research["status"] != "QUALIFIED" or project["status"] != "QUALIFIED":
            raise RuntimeError("Synthetic qualification generation failed.")
        workspace = WorkspaceStore().open(root)
        objects = FilesystemSourceObjectStore(workspace)
        objects.put(b"Synthetic PEOS v1 release evidence.\n")
        result = FilesystemHardeningRepository(workspace).create_backup(output, False)
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
