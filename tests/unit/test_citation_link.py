"""Claim extraction, citation binding, and the behaviour detectors.

This is the module the whole project is a response to, so its failure modes are
tested explicitly rather than by example.
"""

from __future__ import annotations

import pytest

from rag_eval.citation.link import (
    bind_citations,
    detect_abstention,
    detect_clarification,
    extract_labels,
    split_claims,
    strip_labels,
)
from rag_eval.types import Chunk, ScoredChunk


def _scored(chunk_id: str, doc_id: str, text: str, start: int = 0) -> ScoredChunk:
    return ScoredChunk(
        chunk=Chunk(
            chunk_id=chunk_id,
            doc_id=doc_id,
            text=text,
            char_start=start,
            char_end=start + len(text),
        ),
        rank=1,
        score=1.0,
    )


# --- label parsing -----------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "text,expected",
    [
        ("The rate is 2.9% [C1].", ("C1",)),
        ("Both apply [C1][C3].", ("C1", "C3")),
        ("Combined [C2, C4].", ("C2", "C4")),
        ("Lowercase [c5].", ("C5",)),
        ("Repeated [C1] and again [C1].", ("C1",)),
        ("No citations here.", ()),
    ],
)
def test_extract_labels(text, expected) -> None:
    assert extract_labels(text) == expected


@pytest.mark.unit
def test_strip_labels_leaves_readable_prose() -> None:
    assert strip_labels("The rate is 2.9% [C1] plus $0.30 [C2].") == "The rate is 2.9% plus $0.30."


# --- claim segmentation ------------------------------------------------------


@pytest.mark.unit
def test_bullets_are_separate_claims() -> None:
    """Three fees in a list are three assertions.

    Scoring them as one would let two wrong fees hide behind one right one.
    """
    answer = "Fees:\n- Cards are 2.9% [C1]\n- Transfers are 1% [C2]\n- Crypto is 1.5% [C3]"
    claims = split_claims(answer)
    bullets = [c for c in claims if c.text.startswith("-")]
    assert len(bullets) == 3
    assert [c.cited_labels for c in bullets] == [("C1",), ("C2",), ("C3",)]


@pytest.mark.unit
def test_abbreviations_do_not_split_a_sentence() -> None:
    """Over-eager splitting fragments a claim; over-eager merging hides one."""
    claims = split_claims("Cards cost approx. 2.9% [C1]. Transfers cost 1% [C2].")
    assert len(claims) == 2


@pytest.mark.unit
def test_claim_offsets_locate_the_text_in_the_answer() -> None:
    """The demo highlights these spans; wrong offsets highlight the wrong text."""
    answer = "The rate is 2.9% [C1]. Payouts take T+2 days [C2]."
    for claim in split_claims(answer):
        assert answer[claim.char_start : claim.char_end].strip() == claim.text.strip()


# --- binding -----------------------------------------------------------------


@pytest.mark.unit
def test_citations_resolve_to_source_spans() -> None:
    """The property the predecessor project lacked entirely."""
    claims = split_claims("The card rate is 2.9% + $0.30 [C1].")
    retrieved = [_scored("pricing#aa", "pricing-and-fees", "rate is 2.9% + $0.30", start=120)]
    citations, unresolved = bind_citations(
        claims, {"C1": "pricing#aa"}, retrieved, {"pricing-and-fees": "x" * 200}
    )

    assert not unresolved
    assert len(citations) == 1
    c = citations[0]
    assert c.resolved and c.doc_id == "pricing-and-fees"
    assert (c.source_char_start, c.source_char_end) == (120, 140)


@pytest.mark.unit
def test_fabricated_citations_are_recorded_not_dropped() -> None:
    """A label for a source the model was never given is the headline failure.

    Dropping it would report zero fabricated citations, which is precisely the
    number a naive implementation reports.
    """
    claims = split_claims("The rate is 2.9% [C1]. Payouts are T+2 [C9].")
    retrieved = [_scored("pricing#aa", "pricing-and-fees", "2.9%")]
    citations, unresolved = bind_citations(
        claims, {"C1": "pricing#aa"}, retrieved, {"pricing-and-fees": "2.9%"}
    )

    assert unresolved == ["C9"]
    assert len(citations) == 2
    fabricated = [c for c in citations if not c.resolved]
    assert len(fabricated) == 1
    assert fabricated[0].label == "C9"
    assert fabricated[0].chunk_id is None


@pytest.mark.unit
def test_binding_uses_only_what_the_model_was_shown() -> None:
    """The fix for the predecessor's core defect.

    There, sources came from a second retrieval pass and could differ from the
    context that produced the answer. Binding against context_labels makes that
    impossible by construction: a chunk retrieved but not shown cannot be cited.
    """
    claims = split_claims("A fact [C2].")
    retrieved = [
        _scored("shown#aa", "pricing-and-fees", "shown text"),
        _scored("hidden#bb", "payout-schedules", "not shown to the model"),
    ]
    citations, unresolved = bind_citations(
        claims,
        {"C1": "shown#aa"},  # C2 was never in the context
        retrieved,
        {"pricing-and-fees": "shown text", "payout-schedules": "not shown to the model"},
    )
    assert unresolved == ["C2"]
    assert all(c.doc_id != "payout-schedules" for c in citations)


@pytest.mark.unit
def test_document_level_authority_is_deprecated_trace_metadata() -> None:
    """It cannot establish authority for a claim, fact, and effective date."""
    claims = split_claims("A fact [C1].")
    retrieved = [_scored("x#aa", "unknown-doc", "text")]
    citations, _ = bind_citations(claims, {"C1": "x#aa"}, retrieved, {"unknown-doc": "text"})
    assert citations[0].authoritative is None


# --- behaviour detectors -----------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "answer,expected",
    [
        ("The documentation provided does not answer this question.", True),
        ("The excerpts do not contain information about mobile SDKs.", True),
        ("I cannot answer that from the excerpts.", True),
        ("No information about uptime is present.", True),
        ("This is not documented anywhere.", True),
        # The regression that motivated detector version 3. A complete, correct,
        # non-abstaining answer that happens to negate something about NovaPay.
        ("NovaPay does not provide tax advice, but the card rate is 2.9% + $0.30 [C1].", False),
        ("NovaPay does not lend or advance funds [C2].", False),
        ("The card rate is 2.9% + $0.30 [C1].", False),
        ("Declined transactions are free [C1].", False),
    ],
)
def test_abstention_detection(answer, expected) -> None:
    assert detect_abstention(answer) is expected, answer


@pytest.mark.unit
@pytest.mark.parametrize(
    "answer,expected",
    [
        ("It depends on your plan. Which plan are you on?", True),
        ("It depends on the region: $5,000 in the EEA, $10,000 elsewhere. Which applies?", True),
        ("The rate is 2.9%.", False),
        # A bare hedge with no follow-through is not a clarification.
        ("That depends.", False),
    ],
)
def test_clarification_detection(answer, expected) -> None:
    assert detect_clarification(answer) is expected, answer
