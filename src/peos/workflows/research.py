"""Fixed three-step plain-text Research Compiler workflow."""

from peos.domain.workflows.model import StepDefinition, WorkflowDefinition

WORKFLOW = WorkflowDefinition(
    "research.compile-plain-text",
    "1.0.0",
    (
        StepDefinition(1, "ingest-research-inputs", "1.0.0", "REVERSIBLE_WRITE"),
        StepDefinition(
            2, "extract-candidate-claims", "1.0.0", "READ_ONLY", max_output_bytes=262144
        ),
        StepDefinition(3, "commit-research-map", "1.0.0", "REVERSIBLE_WRITE"),
    ),
)
