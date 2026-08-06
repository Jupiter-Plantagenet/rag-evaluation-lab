"""Dataset integrity, enforced in CI.

The failure mode this guards against is specific: a malformed or stale case does
not crash, it produces a metric. A quote that no longer resolves yields zero
retrieval credit and looks like a pipeline regression; a renamed fact_id yields
zero fact coverage and looks like an answer-quality regression. Both would be
misattributed to the thing under test, which is the one mistake an evaluation
harness cannot afford.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET = REPO_ROOT / "data" / "eval" / "novapay_v1.yaml"
CORPUS = REPO_ROOT / "data" / "corpus" / "novapay"
SCHEMA = REPO_ROOT / "data" / "eval" / "schemas" / "eval_case.v1.schema.json"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from validate_dataset import load_corpus, resolve_quote, validate  # noqa: E402


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return yaml.safe_load(DATASET.read_text(encoding="utf-8"))["cases"]


@pytest.mark.unit
def test_all_dataset_invariants_hold() -> None:
    errors = validate(DATASET, CORPUS, SCHEMA)
    assert not errors, "Dataset validation failed:\n" + "\n".join(f"  {e}" for e in errors)


@pytest.mark.unit
def test_every_evidence_quote_resolves_to_its_document(cases: list[dict]) -> None:
    """Localised so a corpus edit names the exact case it broke.

    Character offsets are derived from these quotes at load time, so a quote
    that does not resolve has no offsets -- meaning the case cannot be scored on
    retrieval at all, silently.
    """
    corpus = load_corpus(CORPUS)
    for case in cases:
        for i, span in enumerate(case.get("expected_evidence_spans") or []):
            span_range = resolve_quote(corpus[span["doc_id"]], span["quote"])
            assert span_range is not None, (
                f"{case['id']} span[{i}]: quote does not resolve in {span['doc_id']}.md\n"
                f"  {span['quote'][:100]!r}"
            )
            start, end = span_range
            assert 0 <= start < end <= len(corpus[span["doc_id"]])


@pytest.mark.unit
def test_dataset_meets_its_declared_distribution(cases: list[dict]) -> None:
    counts = Counter(c["category"] for c in cases)
    assert len(cases) >= 30
    assert counts["factual"] >= 10
    assert counts["multi_hop"] >= 5
    assert counts["aggregation"] >= 4
    assert counts["unanswerable"] >= 4
    assert counts["ambiguous"] >= 3
    assert counts["temporal"] >= 2
    assert counts["citation_stress"] >= 2


@pytest.mark.unit
def test_split_is_stratified_across_every_category(cases: list[dict]) -> None:
    """A category confined to one split contributes nothing to the comparison.

    If every unanswerable case were in dev, held-out abstention would be
    unmeasurable while looking fully covered in the category table.
    """
    by_cat: dict[str, set[str]] = {}
    for c in cases:
        by_cat.setdefault(c["category"], set()).add(c["split"])
    single = {k: v for k, v in by_cat.items() if len(v) == 1 and len(v) > 0}
    counts = Counter(c["category"] for c in cases)
    offenders = {k: v for k, v in single.items() if counts[k] > 1}
    assert not offenders, f"categories confined to one split: {offenders}"


@pytest.mark.unit
def test_held_out_split_is_large_enough_to_report(cases: list[dict]) -> None:
    """A floor, not a claim of adequacy.

    n=15 is small and the report says so. This asserts it has not silently got
    smaller -- a shrinking held-out set would widen every confidence interval
    while the headline numbers kept their shape.
    """
    n_test = sum(1 for c in cases if c["split"] == "test")
    assert n_test >= 12, f"held-out split is only {n_test} cases"


@pytest.mark.unit
def test_unanswerable_cases_are_correctly_shaped(cases: list[dict]) -> None:
    """Belt-and-braces over the schema's conditional.

    These three properties together are what stop 'unanswerable' from drifting
    into 'the author could not find an answer'.
    """
    for c in cases:
        if c["answerable"]:
            continue
        assert c.get("gap_id"), f"{c['id']}: unanswerable without a declared gap_id"
        assert c["reference_answer"] is None, f"{c['id']}: unanswerable but has a reference answer"
        assert c["expected_abstention_behaviour"] == "abstain", f"{c['id']}: should expect abstention"
        assert c["forbidden_or_unsupported_claims"], (
            f"{c['id']}: an unanswerable case must name the wrong answers it is testing for, "
            f"or a hallucination cannot be distinguished from an acceptable hedge."
        )


@pytest.mark.unit
def test_ambiguous_cases_expect_clarification_not_abstention(cases: list[dict]) -> None:
    """The distinction the three-valued abstention field exists to preserve.

    An ambiguous question HAS an answer in the corpus -- several, in fact. The
    right behaviour is to surface the conditionality, not to decline. Collapsing
    clarify into abstain would score a correct clarification as a failure.
    """
    for c in cases:
        if c["category"] != "ambiguous":
            continue
        assert c["answerable"] is True, f"{c['id']}: ambiguous cases are answerable, not unanswerable"
        assert c["expected_abstention_behaviour"] == "clarify"


@pytest.mark.unit
def test_multi_hop_cases_genuinely_span_documents(cases: list[dict]) -> None:
    for c in cases:
        if c["category"] != "multi_hop":
            continue
        docs = {s["doc_id"] for s in c["expected_evidence_spans"]}
        assert len(docs) >= 2, (
            f"{c['id']} is labelled multi_hop but all its evidence is in {docs}. "
            f"A single-document case is not multi-hop whatever it is labelled."
        )


@pytest.mark.unit
def test_every_case_records_what_it_is_testing(cases: list[dict]) -> None:
    """scoring_notes are written before any result exists.

    That ordering matters: notes written after seeing an output become a
    rationalisation of what the pipeline happened to do.
    """
    for c in cases:
        assert len(c.get("scoring_notes", "")) >= 40, f"{c['id']}: scoring_notes too thin"
