from pathlib import Path
from typing import Any, cast

import pytest

from peos.bootstrap import open_run_workspace
from peos.domain.errors import ModelCallOutcomeUnknown, ProtocolIntegrityError
from peos.ports.fault_injector import SimulatedInterruption, SingleCheckpointFaultInjector
from tests.integration.test_model_workflow import workspace


def test_durable_response_audit_is_reused_without_call(tmp_path: Path) -> None:
    root, source_id = workspace(tmp_path)
    interrupted = open_run_workspace(
        root, SingleCheckpointFaultInjector("after_model_response_audited")
    )
    with pytest.raises(SimulatedInterruption):
        interrupted.start("sample.mock-summarize-concept", source_id)
    run_id = next((root / ".peos" / "runs").iterdir()).name
    before = sum(event.type == "model.call_started" for event in interrupted._runs.events(run_id))
    resumed = open_run_workspace(root).resume(run_id)
    after = sum(event.type == "model.call_started" for event in interrupted._runs.events(run_id))
    assert resumed["state"] == "SUCCEEDED"
    assert before == after == 1


def test_unknown_call_outcome_is_not_retried(tmp_path: Path) -> None:
    root, source_id = workspace(tmp_path)
    service = open_run_workspace(root)

    def fail_generate(request: object) -> object:
        del request
        raise RuntimeError("uncertain provider boundary")

    assert service._modeling is not None
    gateway = cast(Any, service._modeling._gateway)
    gateway.generate = fail_generate
    with pytest.raises(RuntimeError):
        service.start("sample.mock-summarize-concept", source_id)
    run_id = next((root / ".peos" / "runs").iterdir()).name
    with pytest.raises(ModelCallOutcomeUnknown):
        open_run_workspace(root).resume(run_id)


def test_changed_frozen_protocol_blocks_resume(tmp_path: Path) -> None:
    root, source_id = workspace(tmp_path)
    stopped = open_run_workspace(root).start(
        "sample.mock-summarize-concept", source_id, "mock-summarize-concept"
    )
    protocol = root / "protocols" / "sample.concept-summary" / "1.0.0.md"
    protocol.write_text(protocol.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
    with pytest.raises(ProtocolIntegrityError):
        open_run_workspace(root).resume(str(stopped["run_id"]))
