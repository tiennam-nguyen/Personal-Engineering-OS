"""Fixed two-step cross-workflow bridge."""

from peos.domain.workflows.model import StepDefinition, WorkflowDefinition

WORKFLOW = WorkflowDefinition(
    "crossflow.bridge",
    "1.0.0",
    (
        StepDefinition(1, "resolve-crossflow-inputs", "1.0.0", "REVERSIBLE_WRITE"),
        StepDefinition(2, "commit-crossflow-output", "1.0.0", "REVERSIBLE_WRITE"),
    ),
)
