"""Fixed Project Compiler and result-acceptance workflows."""

from peos.domain.workflows.model import StepDefinition, WorkflowDefinition

COMPILE_WORKFLOW = WorkflowDefinition(
    "project.compile",
    "1.0.0",
    (
        StepDefinition(1, "snapshot-project-inputs", "1.0.0", "REVERSIBLE_WRITE"),
        StepDefinition(2, "draft-project-charter", "1.0.0", "READ_ONLY"),
        StepDefinition(3, "commit-project-packet", "1.0.0", "REVERSIBLE_WRITE"),
    ),
)

RESULT_WORKFLOW = WorkflowDefinition(
    "project.accept-codex-result",
    "1.0.0",
    (
        StepDefinition(1, "validate-codex-result", "1.0.0", "READ_ONLY"),
        StepDefinition(2, "commit-project-map-update", "1.0.0", "REVERSIBLE_WRITE"),
    ),
)
