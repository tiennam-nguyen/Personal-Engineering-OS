"""Fixed in-process workflow registry."""

from peos.domain.errors import ValidationError
from peos.domain.workflows.model import WorkflowDefinition
from peos.workflows.crossflow import WORKFLOW as CROSSFLOW_WORKFLOW
from peos.workflows.evaluation import WORKFLOW as EVALUATION_WORKFLOW
from peos.workflows.learning import ATTEMPT_WORKFLOW
from peos.workflows.learning import COMPILE_WORKFLOW as LEARNING_WORKFLOW
from peos.workflows.mock_summary import WORKFLOW as MOCK_SUMMARY_WORKFLOW
from peos.workflows.project import COMPILE_WORKFLOW, RESULT_WORKFLOW
from peos.workflows.research import WORKFLOW as RESEARCH_WORKFLOW
from peos.workflows.sample import WORKFLOW


def get(name: str) -> WorkflowDefinition:
    workflows = {
        WORKFLOW.name: WORKFLOW,
        MOCK_SUMMARY_WORKFLOW.name: MOCK_SUMMARY_WORKFLOW,
        RESEARCH_WORKFLOW.name: RESEARCH_WORKFLOW,
        COMPILE_WORKFLOW.name: COMPILE_WORKFLOW,
        RESULT_WORKFLOW.name: RESULT_WORKFLOW,
        LEARNING_WORKFLOW.name: LEARNING_WORKFLOW,
        ATTEMPT_WORKFLOW.name: ATTEMPT_WORKFLOW,
        CROSSFLOW_WORKFLOW.name: CROSSFLOW_WORKFLOW,
        EVALUATION_WORKFLOW.name: EVALUATION_WORKFLOW,
    }
    try:
        return workflows[name]
    except KeyError as error:
        raise ValidationError("Workflow is not registered.") from error
