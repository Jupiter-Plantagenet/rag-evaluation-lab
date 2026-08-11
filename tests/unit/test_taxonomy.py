"""The failure taxonomy's ordering, which is the methodology.

The classifier's value comes from being arguable: a reader who disagrees with a
classification should be able to point at a rule. That only holds if the rules
behave as documented, so these tests pin the ordering rather than the outputs.

The load-bearing property is that RETRIEVAL is checked before GENERATION. A
generation error downstream of a retrieval miss is not an independent defect, and
counting both would make the taxonomy add up to more failures than there were.
"""

from __future__ import annotations

from typing import Any

import pytest

from rag_eval.evaluation.taxonomy import (
    FAILURE_CLASSES,
    classify,
    classify_run,
    taxonomy_counts,
)
from rag_eval.types import AbstentionBehaviour, EvalCase, EvidenceSpan, RequiredFact, Split


def make_case(**kw: Any) -> EvalCase:
    defaults: dict[str, Any] = {
        "id": "X-01",
        "category": "factual",
        "question": "q?",
        "answerable": True,
        "expected_abstention_behaviour": AbstentionBehaviour.ANSWER,
        "split": Split.DEV,
        "expected_document_ids": ("doc-a",),
        "expected_evidence_spans": (
            EvidenceSpan(doc_id="doc-a", quote="q", char_start=0, char_end=10),
        ),
        "required_facts": (RequiredFact(fact_id="f", matcher={"kind": "literal", "value": "x"}),),
    }
    defaults.update(kw)
    return EvalCase(**defaults)


def record(**metrics: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "recall_at_5": 1.0,
        "required_fact_coverage": 1.0,
        "abstention_expected": "answer",
        "abstention_observed": "answer",
        "abstention_correct": True,
        "n_fabricated": 0,
        "forbidden_claims": 0,
        "n_non_authoritative": 0,
        "claim_citation_coverage": 1.0,
    }
    base.update(metrics)
    return {"errors": [], "metrics": base, "retrieved": [{"doc_id": "doc-a"}]}


@pytest.mark.unit
def test_a_clean_case_is_not_a_failure() -> None:
    result = classify(record(), make_case())
    assert result.failed is False
    assert result.primary is None


@pytest.mark.unit
def test_pipeline_error_outranks_every_other_signal() -> None:
    """Nothing downstream of a crash is interpretable."""
    rec = record(recall_at_5=0.0, forbidden_claims=3, abstention_correct=False)
    rec["errors"] = ["boom"]
    assert classify(rec, make_case()).primary == "pipeline_error"


@pytest.mark.unit
def test_retrieval_miss_outranks_a_generation_failure_on_the_same_case() -> None:
    """The property the whole ordering exists for.

    This case both missed its evidence AND produced a forbidden claim. Filing it
    as `unsupported_claim` would report a generation defect caused by a retrieval
    defect, and counting both would double-count one problem.
    """
    result = classify(record(recall_at_5=0.0, forbidden_claims=2), make_case())
    assert result.primary == "retrieval_miss"


@pytest.mark.unit
def test_partial_retrieval_splits_by_category() -> None:
    partial = record(recall_at_5=0.5)
    assert (
        classify(partial, make_case(category="multi_hop")).primary == "retrieval_partial_multihop"
    )
    assert (
        classify(partial, make_case(category="aggregation")).primary == "retrieval_partial_multihop"
    )
    assert classify(partial, make_case(category="factual")).primary == "evidence_ranked_low"


@pytest.mark.unit
def test_behavioural_classes_require_retrieval_to_have_succeeded_first() -> None:
    """Documents the reachability limit that makes over_abstention rare.

    An over-abstention on a case that also missed evidence is filed under
    retrieval. That is deliberate, and it is why the taxonomy's behavioural counts
    are lower than the abstention confusion table's -- the two answer different
    questions.
    """
    missed_and_abstained = record(
        recall_at_5=0.0, abstention_observed="abstain", abstention_correct=False
    )
    assert classify(missed_and_abstained, make_case()).primary == "retrieval_miss"

    retrieved_and_abstained = record(
        recall_at_5=1.0, abstention_observed="abstain", abstention_correct=False
    )
    assert classify(retrieved_and_abstained, make_case()).primary == "over_abstention"


@pytest.mark.unit
def test_failed_abstention_and_ambiguity_collapse() -> None:
    unanswerable = make_case(
        answerable=False,
        expected_abstention_behaviour=AbstentionBehaviour.ABSTAIN,
        expected_evidence_spans=(),
        required_facts=(),
        expected_document_ids=(),
    )
    rec = record(
        recall_at_5=None,
        required_fact_coverage=None,
        abstention_expected="abstain",
        abstention_observed="answer",
        abstention_correct=False,
    )
    assert classify(rec, unanswerable).primary == "failed_abstention"

    ambiguous = make_case(
        category="ambiguous", expected_abstention_behaviour=AbstentionBehaviour.CLARIFY
    )
    rec2 = record(
        abstention_expected="clarify", abstention_observed="answer", abstention_correct=False
    )
    assert classify(rec2, ambiguous).primary == "ambiguity_collapse"


@pytest.mark.unit
def test_version_confusion_is_diagnosed_before_generic_unsupported_claim() -> None:
    """Folding this into `unsupported_claim` would lose the diagnosis."""
    rec = record(forbidden_claims=1)
    assert classify(rec, make_case(category="temporal")).primary == "policy_version_confusion"
    assert classify(rec, make_case(category="factual")).primary == "unsupported_claim"


@pytest.mark.unit
def test_fabricated_citation_is_classified_before_answer_content() -> None:
    rec = record(n_fabricated=1, forbidden_claims=1)
    assert classify(rec, make_case()).primary == "citation_unresolvable"


@pytest.mark.unit
def test_partial_fact_coverage_splits_by_category() -> None:
    partial = record(required_fact_coverage=0.5)
    assert classify(partial, make_case(category="aggregation")).primary == "aggregation_error"
    assert classify(partial, make_case(category="factual")).primary == "incomplete_answer"


@pytest.mark.unit
def test_a_correct_abstention_on_an_unanswerable_case_is_not_a_failure() -> None:
    """Undefined recall and coverage must not drag it into the failure set."""
    unanswerable = make_case(
        answerable=False,
        expected_abstention_behaviour=AbstentionBehaviour.ABSTAIN,
        expected_evidence_spans=(),
        required_facts=(),
        expected_document_ids=(),
    )
    rec = record(
        recall_at_5=None,
        required_fact_coverage=None,
        abstention_expected="abstain",
        abstention_observed="abstain",
    )
    assert classify(rec, unanswerable).failed is False


@pytest.mark.unit
def test_counts_include_every_class_even_at_zero() -> None:
    """A taxonomy that lists only what happened reads as a highlight reel."""
    cases = {"X-01": make_case()}
    records = [{"case_id": "X-01", **record(recall_at_5=0.0)}]
    counts = taxonomy_counts(classify_run(records, cases))

    assert set(counts) == set(FAILURE_CLASSES), "every declared class must appear"
    assert counts["retrieval_miss"] == 1
    assert counts["aggregation_error"] == 0
    assert sum(counts.values()) == 1, "each failure contributes exactly one primary class"


@pytest.mark.unit
def test_every_class_the_rules_can_emit_is_declared() -> None:
    """A primary class missing from FAILURE_CLASSES would vanish from reports."""
    scenarios = [
        (record(recall_at_5=0.0), make_case()),
        (record(recall_at_5=0.5), make_case(category="multi_hop")),
        (record(recall_at_5=0.5), make_case()),
        (record(forbidden_claims=1), make_case(category="temporal")),
        (record(n_fabricated=1), make_case()),
        (record(forbidden_claims=1), make_case()),
        (record(required_fact_coverage=0.5), make_case(category="aggregation")),
        (record(required_fact_coverage=0.5), make_case()),
    ]
    for rec, case in scenarios:
        result = classify(rec, case)
        assert result.primary in FAILURE_CLASSES, f"undeclared class {result.primary!r}"
