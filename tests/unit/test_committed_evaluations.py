from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from peos.adapters.filesystem.evaluation_repository import FilesystemEvaluationSuiteRepository
from peos.bootstrap import initialize_workspace, open_evaluation_workspace
from peos.domain.evaluations import suite_fingerprint
from tests.integration.test_evaluation_workflow import PROTOCOL as SUMMARY_PROTOCOL
from tests.project_support import PROTOCOL as PROJECT_PROTOCOL
from tests.research_support import PROTOCOL as RESEARCH_PROTOCOL

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_MODEL_TASKS = {"summarization", "claim_extraction", "project_planning"}


def test_committed_eval_registry_loads_and_hashes_every_active_asset() -> None:
    suites = FilesystemEvaluationSuiteRepository(REPOSITORY_ROOT).list_active()
    assert suites
    assert all(suite.raw_hash.startswith("sha256:") for suite in suites)
    assert all(suite.cases for suite in suites)
    assert all(case.raw_hash.startswith("sha256:") for suite in suites for case in suite.cases)


def test_every_production_model_task_has_one_active_qualification_suite() -> None:
    suites = FilesystemEvaluationSuiteRepository(REPOSITORY_ROOT).list_active()
    assert {suite.task_kind for suite in suites} == PRODUCTION_MODEL_TASKS
    assert len(suites) == len(PRODUCTION_MODEL_TASKS)


def test_committed_goldens_are_static_files_without_candidate_generation() -> None:
    case_files = sorted((REPOSITORY_ROOT / "evals" / "suites").glob("*/cases/*.yaml"))
    assert case_files
    forbidden = ("generate(", "gateway.generate", "parsed_output", "response.content")
    for case_file in case_files:
        raw = case_file.read_text(encoding="utf-8")
        assert "expected:" in raw
        assert not any(marker in raw for marker in forbidden)


def test_committed_suite_fingerprints_are_deterministic() -> None:
    repository = FilesystemEvaluationSuiteRepository(REPOSITORY_ROOT)
    first = {suite.name: suite_fingerprint(suite) for suite in repository.list_active()}
    second = {suite.name: suite_fingerprint(suite) for suite in repository.list_active()}
    assert first == second


def test_committed_suites_qualify_the_exact_production_routes(tmp_path: Path) -> None:
    initialize_workspace(tmp_path)
    shutil.copytree(REPOSITORY_ROOT / "evals", tmp_path / "evals")
    protocols = (
        ("sample.concept-summary", "summarization", "sample.concept_summary.v1", SUMMARY_PROTOCOL),
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
    registry = ["schema_version: 1", "protocols:"]
    for name, task, contract, content in protocols:
        path = tmp_path / "protocols" / name / "1.0.0.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")
        digest = "sha256:" + hashlib.sha256(content.encode()).hexdigest()
        registry.extend(
            [
                f"  - name: {name}",
                "    version: 1.0.0",
                f"    path: protocols/{name}/1.0.0.md",
                f"    sha256: {digest}",
                f"    task_kinds: [{task}]",
                f"    output_contracts: [{contract}]",
                "    sensitivity_ceiling: private",
                "    status: active",
            ]
        )
    (tmp_path / "protocols" / "registry.yaml").write_text(
        "\n".join(registry) + "\n", encoding="utf-8", newline=""
    )
    service = open_evaluation_workspace(tmp_path)
    routes = (
        ("model.summarization.core", "deterministic-concept-summary-v1"),
        ("model.claim-extraction.core", "deterministic-claim-extractor-v1"),
        ("model.project-planning.core", "deterministic-project-planner-v1"),
    )
    assert [service.start(suite, "mock", model, "1")["status"] for suite, model in routes] == [
        "QUALIFIED",
        "QUALIFIED",
        "QUALIFIED",
    ]
