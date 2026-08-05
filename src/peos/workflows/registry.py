"""Fixed in-process workflow registry."""

from peos.domain.errors import ValidationError
from peos.domain.workflows.model import WorkflowDefinition
from peos.workflows.sample import WORKFLOW


def get(name: str) -> WorkflowDefinition:
    if name != WORKFLOW.name:
        raise ValidationError("Only sample.derive-concept is registered.")
    return WORKFLOW
