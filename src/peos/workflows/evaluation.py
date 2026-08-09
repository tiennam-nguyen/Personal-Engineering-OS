"""Frozen route-evaluation workflow metadata."""

from peos.domain.workflows.model import StepDefinition, WorkflowDefinition

WORKFLOW = WorkflowDefinition(
    "system.evaluate-model-route",
    "1.0.0",
    (
        StepDefinition(1, "freeze-eval-suite", "1.0.0", "REVERSIBLE_WRITE", 1, 1048576),
        StepDefinition(2, "execute-eval-cases", "1.0.0", "EXTERNAL_CALL", 1, 1048576),
        StepDefinition(3, "commit-eval-report", "1.0.0", "REVERSIBLE_WRITE", 1, 1048576),
    ),
)
