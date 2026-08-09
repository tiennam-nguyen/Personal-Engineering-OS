from __future__ import annotations

import pytest

from peos.domain.errors import ProjectRequestInvalid, ValidationError
from peos.domain.project.artifacts import validate_project_payload
from peos.domain.project.model import parse_project_request


def test_project_request_is_strict_and_scope_bounded() -> None:
    with pytest.raises(ProjectRequestInvalid):
        parse_project_request({"schema_version": 1})
    with pytest.raises(ProjectRequestInvalid):
        from tests.project_support import project_workspace

        del project_workspace
        parse_project_request({})


def test_project_payload_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        validate_project_payload("project.map", {"schema_version": 1, "extra": True}, "body\n")
