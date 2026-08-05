"""Context policies, blocks and deterministic fingerprints."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from peos.domain.runs.model import sha256


@dataclass(frozen=True)
class ContextPolicy:
    max_blocks: int = 5
    max_context_bytes: int = 32768
    sensitivity_ceiling: str = "private"
    allow_lexical_search: bool = True
    lexical_limit: int = 5
    allow_summaries: bool = False
    allow_truncation: bool = False


@dataclass(frozen=True)
class ContextBlock:
    artifact_id: str
    revision: str
    type: str
    trust: str
    sensitivity: str
    selected_by: str
    locator: str
    byte_count: int
    content: str


def mock_token_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def context_fingerprint(
    policy: ContextPolicy, blocks: tuple[ContextBlock, ...], excluded: tuple[dict[str, str], ...]
) -> str:
    data = {
        "context_schema_version": 1,
        "policy": asdict(policy),
        "blocks": [
            {key: value for key, value in asdict(block).items() if key != "content"}
            for block in blocks
        ],
        "excluded_blocks": list(excluded),
        "totals": {
            "included_blocks": len(blocks),
            "excluded_blocks": len(excluded),
            "context_bytes": sum(block.byte_count for block in blocks),
            "estimated_tokens": mock_token_count("\n".join(block.content for block in blocks)),
            "token_estimate_method": "mock_whitespace_v1",
        },
        "truncation_decisions": [],
    }
    return sha256(data)
