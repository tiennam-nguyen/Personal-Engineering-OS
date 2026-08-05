from pathlib import Path
from typing import cast

import pytest

from peos.bootstrap import open_research_workspace
from peos.domain.artifacts.model import Artifact
from peos.domain.artifacts.validation import validate_artifact
from peos.domain.errors import ValidationError
from tests.research_support import research_workspace


def test_research_payloads_validate_and_legacy_bytes_omit_payload(tmp_path: Path) -> None:
    root, sources = research_workspace(tmp_path)
    result = open_research_workspace(root).start("Is it effective?", sources)
    for identifier in [
        result["question_id"],
        *cast(list[object], result["source_ids"]),
        *cast(list[object], result["claim_ids"]),
        *cast(list[object], result["contradiction_ids"]),
        result["synthesis_id"],
    ]:
        stored = open_research_workspace(root)._index.get(str(identifier))
        assert (
            open_research_workspace(root)._artifacts.verify(stored.canonical_path).artifact.payload
        )
    synthesis = open_research_workspace(root)._lookup(str(result["synthesis_id"])).artifact
    invalid = Artifact(**{**synthesis.__dict__, "content_hash": None, "payload": {"unknown": True}})
    with pytest.raises(ValidationError):
        validate_artifact(invalid, require_hash=False)


def test_unknown_relation_is_rejected(tmp_path: Path) -> None:
    root, sources = research_workspace(tmp_path)
    result = open_research_workspace(root).start("Question?", sources)
    artifact = open_research_workspace(root)._lookup(str(result["synthesis_id"])).artifact
    invalid = Artifact(
        **{
            **artifact.__dict__,
            "content_hash": None,
            "links": ({"rel": "unknown", "target": str(result["question_id"])},),
        }
    )
    with pytest.raises(ValidationError):
        validate_artifact(invalid, require_hash=False)
