from __future__ import annotations

import pytest

from peos.domain.errors import LearningGraphInvalid
from peos.domain.learning.graph import analyze_graph


def test_graph_closure_depth_and_cycles() -> None:
    concepts = [
        {"id": "a", "prerequisites": []},
        {"id": "b", "prerequisites": ["a"]},
        {"id": "c", "prerequisites": ["b"]},
    ]
    result = analyze_graph(concepts, "c")
    assert result["prerequisite_closure"] == ["a", "b"]
    assert result["depths"] == {"a": 0, "b": 1, "c": 2}
    with pytest.raises(LearningGraphInvalid):
        analyze_graph(
            [{"id": "a", "prerequisites": ["b"]}, {"id": "b", "prerequisites": ["a"]}], "a"
        )
