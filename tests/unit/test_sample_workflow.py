import pytest

from peos.domain.artifacts.model import Artifact, Author, Provenance
from peos.ports.fault_injector import (
    NoOpFaultInjector,
    SimulatedInterruption,
    SingleCheckpointFaultInjector,
)
from peos.workflows.sample import artifact_data, prepare, verify_prepared


def test_sample_workflow_is_deterministic() -> None:
    source = Artifact(
        "art_" + "a" * 32,
        "knowledge.concept",
        1,
        "Input",
        "draft",
        "ws_" + "b" * 32,
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00Z",
        (Author("human", "user"),),
        "private",
        ("one",),
        (),
        Provenance("human", None, ()),
        "sha256:" + "c" * 64,
        "Body\n",
    )
    result = prepare(source, "run_" + "d" * 32, "2026-01-01T00:00:00Z")
    assert result.id == prepare(source, "run_" + "d" * 32, "2026-01-01T00:00:00Z").id
    assert (
        verify_prepared(source, "run_" + "d" * 32, "2026-01-01T00:00:00Z", artifact_data(result))
        == result
    )


def test_noop_fault_injector_never_interrupts() -> None:
    NoOpFaultInjector().checkpoint("anything")


def test_single_checkpoint_interrupts_once_and_only_at_target() -> None:
    injector = SingleCheckpointFaultInjector("target")
    injector.checkpoint("other")
    with pytest.raises(SimulatedInterruption):
        injector.checkpoint("target")
    injector.checkpoint("target")
