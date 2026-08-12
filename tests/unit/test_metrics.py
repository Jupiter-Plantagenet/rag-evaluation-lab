"""Metric definitions, checked against hand-computed values.

Metrics are the instrument. A bug here does not crash anything -- it produces a
number that is wrong in a plausible direction, and every conclusion drawn from
it inherits the error silently. So each is checked against a value worked out by
hand rather than against whatever the code currently returns.
"""

from __future__ import annotations

import math

import pytest

from rag_eval.evaluation.metrics import (
    abstention_outcome,
    bootstrap_ci,
    citation_metrics,
    match_fact,
    mean_ignoring_none,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    required_fact_coverage,
)
from rag_eval.types import (
    AbstentionBehaviour,
    EvalCase,
    EvidenceSpan,
    RequiredFact,
    Split,
)


def make_case(**kw) -> EvalCase:
    defaults = {
        "id": "X-01",
        "category": "factual",
        "question": "q?",
        "answerable": True,
        "expected_abstention_behaviour": AbstentionBehaviour.ANSWER,
        "split": Split.DEV,
    }
    defaults.update(kw)
    return EvalCase(**defaults)  # type: ignore[arg-type]


def chunk(rank: int, doc_id: str, start: int, end: int) -> dict:
    return {"rank": rank, "doc_id": doc_id, "char_start": start, "char_end": end}


# --- retrieval ---------------------------------------------------------------


@pytest.mark.unit
def test_recall_is_span_level_not_binary() -> None:
    """A multi-hop case needing two spans is not fully answered by finding one.

    A binary hit-rate would score this 1.0 and make multi-hop look identical to
    single-hop retrieval.
    """
    case = make_case(
        expected_evidence_spans=(
            EvidenceSpan("doc-a", "q", 100, 200),
            EvidenceSpan("doc-b", "q", 300, 400),
        )
    )
    retrieved = [chunk(1, "doc-a", 90, 250)]
    assert recall_at_k(case, retrieved, 5, 0.5) == 0.5


@pytest.mark.unit
def test_a_chunk_in_the_right_document_that_misses_the_span_is_not_a_hit() -> None:
    """Document-level matching would flatter retrieval on a 14-document corpus,
    where guessing the document is easy and finding the passage is the work."""
    case = make_case(expected_evidence_spans=(EvidenceSpan("doc-a", "q", 100, 200),))
    retrieved = [chunk(1, "doc-a", 900, 1000)]
    assert recall_at_k(case, retrieved, 5, 0.5) == 0.0


@pytest.mark.unit
def test_coverage_threshold_tolerates_chunk_boundaries() -> None:
    """Requiring containment would score correct retrievals as misses purely
    because of where a boundary happened to fall."""
    case = make_case(expected_evidence_spans=(EvidenceSpan("doc-a", "q", 100, 200),))
    partial = [chunk(1, "doc-a", 150, 400)]  # covers 50 of 100 characters
    assert recall_at_k(case, partial, 5, 0.5) == 1.0
    assert recall_at_k(case, partial, 5, 0.9) == 0.0


@pytest.mark.unit
def test_metrics_are_none_when_undefined_never_zero() -> None:
    """None means "not applicable"; 0.0 means "scored and failed".

    Treating an unanswerable case's undefined recall as 0.0 would drag the
    retrieval average down and blame retrieval for it.
    """
    case = make_case(answerable=False, expected_evidence_spans=())
    assert recall_at_k(case, [chunk(1, "d", 0, 10)], 5, 0.5) is None
    assert mrr(case, [chunk(1, "d", 0, 10)], 0.5) is None
    assert precision_at_k(case, [chunk(1, "d", 0, 10)], 5, 0.5) is None


@pytest.mark.unit
def test_mrr_matches_hand_computation() -> None:
    case = make_case(expected_evidence_spans=(EvidenceSpan("doc-a", "q", 100, 200),))
    retrieved = [chunk(1, "doc-b", 0, 50), chunk(2, "doc-c", 0, 50), chunk(3, "doc-a", 100, 200)]
    assert mrr(case, retrieved, 0.5) == pytest.approx(1 / 3)


@pytest.mark.unit
def test_mrr_is_zero_when_nothing_relevant_retrieved() -> None:
    case = make_case(expected_evidence_spans=(EvidenceSpan("doc-a", "q", 100, 200),))
    assert mrr(case, [chunk(1, "doc-z", 0, 50)], 0.5) == 0.0


@pytest.mark.unit
def test_ndcg_rewards_ranking_evidence_higher() -> None:
    case = make_case(expected_evidence_spans=(EvidenceSpan("doc-a", "q", 100, 200),))
    high = ndcg_at_k(case, [chunk(1, "doc-a", 100, 200), chunk(2, "doc-b", 0, 9)], 5, 0.5)
    low = ndcg_at_k(case, [chunk(1, "doc-b", 0, 9), chunk(2, "doc-a", 100, 200)], 5, 0.5)
    assert high == pytest.approx(1.0)
    assert low == pytest.approx(1 / math.log2(3))
    assert high > low


@pytest.mark.unit
def test_ndcg_duplicate_overlapping_chunks_cannot_multiply_one_evidence_unit() -> None:
    case = make_case(expected_evidence_spans=(EvidenceSpan("doc-a", "q", 100, 200),))
    duplicated = [chunk(1, "doc-a", 100, 200), chunk(2, "doc-a", 110, 190)]
    assert ndcg_at_k(case, duplicated, 5, 0.5) == pytest.approx(1.0)


@pytest.mark.unit
def test_ndcg_is_bounded_for_duplicate_and_multihop_evidence() -> None:
    case = make_case(
        expected_evidence_spans=(
            EvidenceSpan("doc-a", "first", 0, 100),
            EvidenceSpan("doc-b", "second", 0, 100),
        )
    )
    retrieved = [
        chunk(1, "doc-a", 0, 100),
        chunk(2, "doc-a", 10, 90),
        chunk(3, "doc-b", 0, 100),
        chunk(4, "doc-b", 10, 90),
    ]
    score = ndcg_at_k(case, retrieved, 5, 0.5)
    assert score is not None and 0.0 <= score <= 1.0
    assert score == pytest.approx((1 + 1 / math.log2(4)) / (1 + 1 / math.log2(3)))


@pytest.mark.unit
def test_precision_falls_as_k_rises() -> None:
    """The trade-off that makes precision worth reporting next to recall."""
    case = make_case(expected_evidence_spans=(EvidenceSpan("doc-a", "q", 0, 100),))
    retrieved = [chunk(1, "doc-a", 0, 100)] + [chunk(i, "doc-z", 0, 10) for i in range(2, 6)]
    assert precision_at_k(case, retrieved, 1, 0.5) == 1.0
    assert precision_at_k(case, retrieved, 5, 0.5) == pytest.approx(0.2)


# --- fact matching -----------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "answer,expected",
    [
        ("The rate is 2.9%", True),
        ("The rate is 2.9 %", True),
        ("The rate is 2.9 per cent", True),
        ("The rate is 3%", False),
        ("The rate is 2.95%", False),
    ],
)
def test_numeric_matcher_parses_numbers_not_strings(answer, expected) -> None:
    """This is what lets an answer be phrased freely and still be checked exactly."""
    assert match_fact(answer, {"kind": "numeric", "value": 2.9, "unit": "percent"}) is expected


@pytest.mark.unit
def test_numeric_tolerance_handles_rounding() -> None:
    m = {"kind": "numeric", "value": 12250, "unit": "usd", "tolerance": 250}
    assert match_fact("about $12,300 per month", m)
    assert not match_fact("about $15,000 per month", m)


@pytest.mark.unit
def test_numeric_matcher_handles_thousands_separators() -> None:
    assert match_fact("$50,000 per month", {"kind": "numeric", "value": 50000, "unit": "usd"})


@pytest.mark.unit
def test_all_of_requires_every_component() -> None:
    """A rate without its fixed component is a wrong quote, not a partial one."""
    m = {
        "kind": "all_of",
        "matchers": [
            {"kind": "numeric", "value": 2.9, "unit": "percent"},
            {"kind": "numeric", "value": 0.30, "unit": "usd", "tolerance": 0.001},
        ],
    }
    assert match_fact("2.9% + $0.30", m)
    assert not match_fact("2.9%", m)


@pytest.mark.unit
def test_absent_matcher_inverts() -> None:
    m = {"kind": "absent", "matcher": {"kind": "literal", "value": "90 days"}}
    assert match_fact("The window is 120 days.", m)
    assert not match_fact("The window is 90 days.", m)


@pytest.mark.unit
def test_required_fact_coverage_is_weighted() -> None:
    case = make_case(
        required_facts=(
            RequiredFact("a", {"kind": "literal", "value": "alpha"}, weight=3.0),
            RequiredFact("b", {"kind": "literal", "value": "beta"}, weight=1.0),
        )
    )
    assert required_fact_coverage(case, "alpha only") == pytest.approx(0.75)
    assert required_fact_coverage(case, "beta only") == pytest.approx(0.25)


# --- abstention --------------------------------------------------------------


@pytest.mark.unit
def test_clarification_is_not_scored_as_a_failed_answer() -> None:
    """The distinction the three-valued field exists to preserve."""
    case = make_case(
        category="ambiguous", expected_abstention_behaviour=AbstentionBehaviour.CLARIFY
    )
    assert abstention_outcome(case, abstained=False, clarified=True).correct
    # Silently picking one reading is the designed failure.
    assert not abstention_outcome(case, abstained=False, clarified=False).correct


@pytest.mark.unit
def test_abstaining_on_an_answerable_question_is_wrong() -> None:
    case = make_case(expected_abstention_behaviour=AbstentionBehaviour.ANSWER)
    assert not abstention_outcome(case, abstained=True, clarified=False).correct


@pytest.mark.unit
def test_abstaining_on_an_unanswerable_question_is_right() -> None:
    case = make_case(answerable=False, expected_abstention_behaviour=AbstentionBehaviour.ABSTAIN)
    assert abstention_outcome(case, abstained=True, clarified=False).correct
    assert not abstention_outcome(case, abstained=False, clarified=False).correct


# --- citations ---------------------------------------------------------------


@pytest.mark.unit
def test_fabricated_citations_lower_validity() -> None:
    case = make_case(expected_document_ids=("doc-a",))
    citations = [
        {"claim_id": "cl0", "resolved": True, "doc_id": "doc-a", "authoritative": True},
        {"claim_id": "cl1", "resolved": False, "doc_id": None, "authoritative": None},
    ]
    claims = [
        {"claim_id": "cl0", "text": "a claim with several words"},
        {"claim_id": "cl1", "text": "another claim with several words"},
    ]
    m = citation_metrics(case, citations, claims)
    assert m["citation_validity"] == 0.5
    assert m["n_fabricated"] == 1


@pytest.mark.unit
def test_claim_coverage_ignores_trivially_short_claims() -> None:
    """A three-word fragment is a sentence-splitter artefact, not an assertion
    that needs its own citation."""
    case = make_case(expected_document_ids=("doc-a",))
    claims = [
        {"claim_id": "cl0", "text": "The card rate is 2.9% plus thirty cents"},
        {"claim_id": "cl1", "text": "Yes."},
    ]
    citations = [{"claim_id": "cl0", "resolved": True, "doc_id": "doc-a", "authoritative": True}]
    assert citation_metrics(case, citations, claims)["claim_citation_coverage"] == 1.0


@pytest.mark.unit
def test_document_level_authority_is_not_a_current_citation_quality_metric() -> None:
    case = make_case(expected_document_ids=("policy-archive-2024",))
    citations = [
        {
            "claim_id": "cl0",
            "resolved": True,
            "doc_id": "policy-archive-2024",
            "authoritative": False,
        }
    ]
    claims = [{"claim_id": "cl0", "text": "A historical policy claim with enough words"}]
    metrics = citation_metrics(case, citations, claims)
    assert "n_non_authoritative" not in metrics


# --- aggregation -------------------------------------------------------------


@pytest.mark.unit
def test_mean_skips_none_rather_than_treating_it_as_zero() -> None:
    assert mean_ignoring_none([1.0, None, 0.0]) == 0.5
    assert mean_ignoring_none([None, None]) is None


@pytest.mark.unit
def test_bootstrap_ci_is_reproducible_and_brackets_the_mean() -> None:
    values = [0.0, 0.5, 1.0, 0.75, 0.25, 0.9, 0.1, 0.6]
    a = bootstrap_ci(values, resamples=2000, seed=42)
    b = bootstrap_ci(values, resamples=2000, seed=42)
    assert a == b, "a seeded CI must reproduce, or the reported interval is not a fact"
    assert a is not None
    assert a[0] <= sum(values) / len(values) <= a[1]


@pytest.mark.unit
def test_bootstrap_returns_none_when_too_few_points() -> None:
    """Better to report nothing than an interval computed from two numbers."""
    assert bootstrap_ci([0.5, 0.6]) is None
