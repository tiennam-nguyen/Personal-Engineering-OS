"""Fixed deterministic Learning Compiler workflows."""

from peos.domain.workflows.model import StepDefinition, WorkflowDefinition

COMPILE_WORKFLOW = WorkflowDefinition(
    "learning.compile",
    "1.0.0",
    (
        StepDefinition(1, "freeze-learning-inputs", "1.0.0", "REVERSIBLE_WRITE"),
        StepDefinition(2, "analyze-learning-gap", "1.0.0", "READ_ONLY"),
        StepDefinition(3, "commit-learning-goal", "1.0.0", "REVERSIBLE_WRITE"),
    ),
)

ATTEMPT_WORKFLOW = WorkflowDefinition(
    "learning.record-attempt",
    "1.0.0",
    (
        StepDefinition(1, "verify-learning-attempt", "1.0.0", "READ_ONLY"),
        StepDefinition(2, "commit-learning-evidence", "1.0.0", "REVERSIBLE_WRITE"),
    ),
)
