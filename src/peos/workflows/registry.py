"""Fixed in-process workflow registry."""

from peos.domain.errors import ValidationError
from peos.domain.workflows.model import WorkflowDefinition
from peos.workflows.mock_summary import WORKFLOW as MOCK_SUMMARY_WORKFLOW
from peos.workflows.research import WORKFLOW as RESEARCH_WORKFLOW
from peos.workflows.sample import WORKFLOW


def get(name: str) -> WorkflowDefinition:
    workflows = {
        WORKFLOW.name: WORKFLOW,
        MOCK_SUMMARY_WORKFLOW.name: MOCK_SUMMARY_WORKFLOW,
        RESEARCH_WORKFLOW.name: RESEARCH_WORKFLOW,
    }
    try:
        return workflows[name]
    except KeyError as error:
        raise ValidationError("Workflow is not registered.") from error
