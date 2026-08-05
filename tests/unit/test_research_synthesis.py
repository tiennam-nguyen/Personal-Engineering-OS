from peos.domain.research.model import NormalizedClaim
from peos.domain.research.synthesis import synthesis_body


def test_synthesis_is_traceable_ordered_and_reports_unreadable() -> None:
    positive = NormalizedClaim(
        "The treatment is effective.", "the treatment is effective", "positive", "CONTESTED", ()
    )
    negative = NormalizedClaim(
        "The treatment is not effective.", "the treatment is effective", "negative", "CONTESTED", ()
    )
    body = synthesis_body(
        (("art_positive", positive), ("art_negative", negative)),
        (("the treatment is effective", "art_positive", "art_negative"),),
        1,
    )
    assert "The evidence is contested." in body
    assert positive.proposition in body and negative.proposition in body
    assert "1 unreadable source segment(s)" in body
    assert "Review the unreadable" in body
