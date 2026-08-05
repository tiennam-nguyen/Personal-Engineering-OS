"""Exact deterministic claim normalization and contradiction discovery."""

from __future__ import annotations

import re
from dataclasses import replace

from peos.domain.errors import ClaimNormalizationError
from peos.domain.research.model import CandidateClaim, NormalizedClaim


def semantic_key(proposition: str) -> str:
    words = [
        word for word in re.sub(r"\s+", " ", proposition.casefold()).split(" ") if word != "not"
    ]
    key = " ".join(words).rstrip(" . , ; : ! ?").strip()
    if not key:
        raise ClaimNormalizationError("Claim semantic key is empty.")
    return key


def normalize_claims(
    candidates: tuple[CandidateClaim, ...],
) -> tuple[tuple[NormalizedClaim, ...], tuple[str, ...]]:
    grouped: dict[tuple[str, str], list[CandidateClaim]] = {}
    for candidate in candidates:
        proposition = re.sub(r"\s+", " ", candidate.proposition).strip()
        key = semantic_key(proposition)
        grouped.setdefault((key, candidate.polarity), []).append(
            replace(candidate, proposition=proposition)
        )
    polarities = {
        key for key, _ in grouped if (key, "positive") in grouped and (key, "negative") in grouped
    }
    claims = tuple(
        NormalizedClaim(
            items[0].proposition,
            key,
            polarity,
            "CONTESTED" if key in polarities else "SUPPORTED",
            tuple(dict.fromkeys(item.locator for item in items)),
        )
        for (key, polarity), items in sorted(grouped.items())
    )
    return claims, tuple(sorted(polarities))
