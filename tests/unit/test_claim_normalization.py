from peos.domain.research.claims import normalize_claims, semantic_key
from peos.domain.research.model import CandidateClaim, SourceLocator


def locator(line: int) -> SourceLocator:
    return SourceLocator(
        "art_" + f"{line:032x}",
        "sha256:" + "a" * 64,
        "sha256:" + "b" * 64,
        line,
        line,
        0,
        1,
        "sha256:" + "c" * 64,
    )


def test_merge_and_opposite_polarity_preserve_evidence() -> None:
    candidates = (
        CandidateClaim("The treatment is effective.", "positive", locator(1)),
        CandidateClaim("The treatment is effective.", "positive", locator(2)),
        CandidateClaim("The treatment is not effective.", "negative", locator(3)),
    )
    claims, contradictions = normalize_claims(candidates)
    assert semantic_key(candidates[0].proposition) == semantic_key(candidates[2].proposition)
    assert len(claims) == 2 and contradictions == ("the treatment is effective",)
    assert sorted(len(claim.evidence_refs) for claim in claims) == [1, 2]
    assert all(claim.evidence_status == "CONTESTED" for claim in claims)


def test_no_fuzzy_merge() -> None:
    assert semantic_key("Treatment is effective") != semantic_key("Therapy works")
