"""Bounded context compilation from independently verified canonical artifacts."""

from __future__ import annotations

from dataclasses import asdict

from peos.domain.context.model import (
    ContextBlock,
    ContextPolicy,
    context_fingerprint,
    mock_token_count,
)
from peos.domain.errors import (
    ContextBudgetExceeded,
    ContextCompilationError,
    SensitivityPolicyViolation,
)
from peos.ports.artifact_index import ArtifactIndex
from peos.ports.artifact_repository import ArtifactRepository

_SENSITIVITY = {"public": 0, "private": 1, "confidential": 2}


class ContextCompiler:
    def __init__(self, repository: ArtifactRepository, index: ArtifactIndex) -> None:
        self._repository = repository
        self._index = index

    def compile(
        self,
        explicit_ids: list[str],
        policy: ContextPolicy = ContextPolicy(),
        lexical_query: str | None = None,
    ) -> tuple[tuple[ContextBlock, ...], dict[str, object], str]:
        if not explicit_ids:
            raise ContextCompilationError("At least one explicit context artifact is required.")
        if len(explicit_ids) > policy.max_blocks:
            raise ContextCompilationError("Explicit context exceeds max blocks.")
        candidates = [(identifier, "explicit") for identifier in explicit_ids]
        if lexical_query and policy.allow_lexical_search:
            candidates += [
                (result.id, "lexical")
                for result in self._index.search(lexical_query, policy.lexical_limit)
            ]
        blocks: list[ContextBlock] = []
        excluded: list[dict[str, str]] = []
        seen = set()
        for identifier, selected_by in candidates:
            if identifier in seen:
                if selected_by == "lexical":
                    excluded.append({"artifact_id": identifier, "reason": "duplicate"})
                continue
            seen.add(identifier)
            try:
                projected = self._index.get(identifier)
                stored = self._repository.verify(projected.canonical_path)
            except Exception as error:
                if selected_by == "explicit":
                    raise ContextCompilationError(
                        "Explicit context artifact is unavailable."
                    ) from error
                continue
            artifact = stored.artifact
            if _SENSITIVITY[artifact.sensitivity] > _SENSITIVITY[policy.sensitivity_ceiling]:
                if selected_by == "explicit":
                    raise SensitivityPolicyViolation(
                        "Explicit context exceeds sensitivity ceiling."
                    )
                excluded.append({"artifact_id": identifier, "reason": "sensitivity_exceeded"})
                continue
            content = f"Title: {artifact.title}\n\n{artifact.body}"
            bytes_ = len(content.encode())
            if bytes_ > policy.max_context_bytes and selected_by == "explicit":
                raise ContextBudgetExceeded("Explicit context block exceeds byte budget.")
            if len(blocks) >= policy.max_blocks:
                if selected_by == "explicit":
                    raise ContextCompilationError("Required explicit context exceeds max blocks.")
                excluded.append({"artifact_id": identifier, "reason": "max_blocks"})
                continue
            if sum(block.byte_count for block in blocks) + bytes_ > policy.max_context_bytes:
                if selected_by == "explicit":
                    raise ContextBudgetExceeded("Explicit context exceeds byte budget.")
                excluded.append({"artifact_id": identifier, "reason": "byte_budget"})
                continue
            blocks.append(
                ContextBlock(
                    artifact.id,
                    artifact.content_hash or "",
                    artifact.type,
                    "workspace_verified",
                    artifact.sensitivity,
                    selected_by,
                    stored.canonical_path,
                    bytes_,
                    content,
                )
            )
        result = tuple(blocks)
        excluded_tuple = tuple(excluded)
        fingerprint = context_fingerprint(policy, result, excluded_tuple)
        manifest = {
            "context_schema_version": 1,
            "policy": asdict(policy),
            "blocks": [
                {key: value for key, value in asdict(block).items() if key != "content"}
                for block in result
            ],
            "excluded_blocks": list(excluded_tuple),
            "totals": {
                "included_blocks": len(result),
                "excluded_blocks": len(excluded_tuple),
                "context_bytes": sum(block.byte_count for block in result),
                "estimated_tokens": mock_token_count("\n".join(block.content for block in result)),
                "token_estimate_method": "mock_whitespace_v1",
            },
            "truncation_decisions": [],
        }
        return result, manifest, fingerprint
