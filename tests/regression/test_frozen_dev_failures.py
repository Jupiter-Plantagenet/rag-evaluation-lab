"""Confirmed dev-split failures, frozen so they cannot silently come back.

Every case below was measured as failing in the frozen BASELINE dev run
(`baseline-dev-20260806T180859Z-66ee099b`) and measured again in the frozen
IMPROVED dev run (`improved-dev-20260806T181347Z-1e6a1bf8`). The numbers quoted
in each docstring are read from those traces, not asserted from memory.

**Every case here is from the DEV split.** None is derived from held-out data.
Building a regression test from a held-out failure would tune the system against
the held-out split by the back door -- more quietly than changing a config, and
just as fatally.

What these tests assert, and what they deliberately do not: they pin the
MECHANISM each intervention was credited with, not the end-to-end score. A score
assertion would need MiniLM embeddings, which CI does not install, and would fail
for reasons unrelated to the property being protected. Chunk structure and BM25
ranking need no embedding model and no network, so they run everywhere.
"""

from __future__ import annotations

import pytest

from rag_eval.ingest.corpus import Corpus
from rag_eval.retrieval.retrievers import BM25Retriever
from rag_eval.types import Chunk

from .conftest import covering_chunks

pytestmark = pytest.mark.regression


# ---------------------------------------------------------------------------
# F-15 -- a table row separated from the header that gives it meaning
# ---------------------------------------------------------------------------

F15_DOC = "subscription-plans"
F15_ROW = "| Dashboard seats | 3 | 15 | unlimited |"
F15_HEADER = "| | Starter | Pro | Enterprise |"


def test_f15_dashboard_seats_row_keeps_its_column_header(
    corpus: Corpus, baseline_chunks: list[Chunk], improved_chunks: list[Chunk]
) -> None:
    """F-15: "How many dashboard seats do I get on Pro?"

    Originating dev case: F-15 (factual).
    Original failure class: unsupported_claim. Baseline MRR 0.333; improved 1.000.

    Why this assertion is meaningful. The evidence is a table ROW whose three
    values -- 3, 15, unlimited -- are meaningless without the column header row
    that says which is Starter, which is Pro and which is Enterprise. Under
    fixed-size chunking the covering chunk begins mid-table, at "0.30 |
    negotiated |", with the header row in a different chunk entirely. A model
    given that chunk can read "3 | 15 | unlimited" and has no way to know that
    Pro is 15. It is precisely the shape of context that produces a confident
    wrong answer rather than a visible failure.

    Which intervention preserves it: intervention 1, structure-aware chunking
    (`chunker.kind = markdown_structure`), which treats a Markdown table as
    atomic and splits on headings rather than character counts.
    """
    baseline_cov = covering_chunks(baseline_chunks, corpus, F15_DOC, F15_ROW)
    improved_cov = covering_chunks(improved_chunks, corpus, F15_DOC, F15_ROW)

    assert baseline_cov, "the row is not covered at all under baseline chunking"
    assert improved_cov, "the row is not covered at all under improved chunking"

    assert not any(F15_HEADER in c.text for c in baseline_cov), (
        "Fixed-size chunking now keeps this row with its header. That is an "
        "improvement, but it means this regression test no longer demonstrates "
        "the failure it was built from -- re-derive it rather than deleting it."
    )
    assert all(F15_HEADER in c.text for c in improved_cov), (
        "REGRESSION: structure-aware chunking has separated the dashboard-seats "
        "row from its column header. The numbers 3/15/unlimited are unlabelled "
        "in the retrieved context and F-15 can be answered confidently and wrong."
    )


def test_f15_improved_chunk_carries_the_heading_path(
    corpus: Corpus, improved_chunks: list[Chunk]
) -> None:
    """The heading path is packed into the context, so it must survive chunking."""
    improved_cov = covering_chunks(improved_chunks, corpus, F15_DOC, F15_ROW)
    assert improved_cov
    for chunk in improved_cov:
        assert chunk.heading_path, "improved chunks must carry a heading path"
        assert "Plan comparison" in chunk.heading_path


# ---------------------------------------------------------------------------
# F-07 -- a rate-limit table whose section heading names what the numbers are
# ---------------------------------------------------------------------------

F07_DOC = "api-authentication"
F07_ROW = "| Starter | **100 requests per second** |"


def test_f07_rate_limit_row_is_scoped_by_its_section_heading(
    corpus: Corpus, baseline_chunks: list[Chunk], improved_chunks: list[Chunk]
) -> None:
    """F-07: "What is the API rate limit on the Starter plan?"

    Originating dev case: F-07 (factual).
    Original failure class: retrieval_miss. Baseline recall@5 0.000 and MRR
    0.000; improved recall@5 1.000 and MRR 1.000 -- the cleanest single
    demonstration in the dev run.

    Why this assertion is meaningful, and a correction. `configs/improved.yaml`
    explains F-07 as the header row being split from the table. That is NOT what
    the traces show: under fixed-size chunking the covering chunk does contain
    "| Plan | Limit |". What it lacks is any heading path at all, and it opens
    with unrelated prose about `403 Forbidden` and key restriction, so the
    numbers sit inside a chunk that is mostly about permissions. The improved
    chunk starts at "## Rate limits" and carries the heading path
    ("API Authentication and Errors", "Rate limits"), which is packed into the
    context the model sees. The mechanism credited with fixing F-07 is section
    scoping, not header preservation. (Recorded in docs/failure-taxonomy.md.)

    Which intervention preserves it: intervention 1, structure-aware chunking.
    """
    baseline_cov = covering_chunks(baseline_chunks, corpus, F07_DOC, F07_ROW)
    improved_cov = covering_chunks(improved_chunks, corpus, F07_DOC, F07_ROW)

    assert baseline_cov and improved_cov

    assert all(not c.heading_path for c in baseline_cov), (
        "fixed-size chunking has started producing heading paths; this test's "
        "premise no longer holds"
    )
    assert all("Rate limits" in c.heading_path for c in improved_cov), (
        "REGRESSION: the Starter rate-limit row is no longer scoped by its "
        "'Rate limits' heading. F-07 regressed to recall 0.000 under exactly "
        "this condition in the baseline run."
    )
    assert all(c.text.lstrip().startswith("## Rate limits") for c in improved_cov), (
        "REGRESSION: the improved chunk no longer begins at the section heading"
    )


# ---------------------------------------------------------------------------
# F-11 -- an evidence span the baseline never retrieved
# ---------------------------------------------------------------------------

F11_DOC = "webhook-delivery"
F11_QUOTE = "An endpoint failing **every** delivery for **7 consecutive days** is d"


def test_f11_endpoint_disabling_span_is_covered_by_exactly_one_chunk(
    corpus: Corpus, improved_chunks: list[Chunk]
) -> None:
    """F-11: "What happens if my endpoint keeps failing? Will NovaPay turn it off?"

    Originating dev case: F-11 (factual).
    Original failure class: retrieval_miss. Baseline recall@5 0.000 AND required
    fact coverage 0.000 -- the baseline retrieved four chunks from the right two
    documents and none of them contained the disabling rule. Improved recall@5
    1.000, fact coverage 1.000.

    Why this assertion is meaningful. This is the case that separates "looked in
    the wrong place" from "looked in the right place and grabbed the wrong
    passage": the baseline's document recall was fine. If the disabling rule ever
    straddles a chunk boundary, no chunk covers 50% of it, span-level recall goes
    to zero, and the answer becomes "the documentation does not say" for a rule
    that is plainly documented.

    Which intervention preserves it: intervention 1, structure-aware chunking,
    which keeps the "Endpoint disabling" subsection whole.
    """
    cov = covering_chunks(improved_chunks, corpus, F11_DOC, F11_QUOTE)
    assert len(cov) == 1, (
        f"REGRESSION: the endpoint-disabling evidence is covered by {len(cov)} "
        "chunks, not 1. Split evidence is what produced F-11's baseline recall of 0.000."
    )
    assert "Endpoint disabling" in cov[0].heading_path


# ---------------------------------------------------------------------------
# M-07 -- multi-hop: all three spans, not one of three
# ---------------------------------------------------------------------------

M07_SPANS = [
    ("regional-restrictions", "| India | **$2,000** | local card-not-present rules |"),
    ("regional-restrictions", "require enhanced due diligence at onboarding"),
    ("account-limits", "it takes **up to 5 business days**"),
]


def test_m07_all_three_evidence_spans_remain_individually_retrievable(
    corpus: Corpus, improved_chunks: list[Chunk]
) -> None:
    """M-07: "I am setting up in India. What is my per-payment ceiling and how
    long will approval take?"

    Originating dev case: M-07 (multi_hop).
    Original failure class: retrieval_partial_multihop. Baseline recall@5 0.333
    -- one span of three -- with MRR 1.000, which is the exact pair of numbers
    that shows why both are reported. A binary hit-rate would have called this
    case solved.

    Why this assertion is meaningful. The three spans live in two documents and
    three different sections. Span-level recall is the metric that distinguishes
    "found one of the three things the question needs" from "answered the
    question", and it only works if each span is independently coverable.

    Which intervention preserves it: intervention 1 (each subsection stays whole)
    together with intervention 3 (top_k raised to 8, so three chunks across two
    documents can all fit in the context budget). The budget half of that is
    audit finding A-13 -- it is a real effect and it is not a ranking effect.
    """
    for doc_id, quote in M07_SPANS:
        cov = covering_chunks(improved_chunks, corpus, doc_id, quote)
        assert len(cov) >= 1, f"REGRESSION: no chunk covers the M-07 span in {doc_id}: {quote!r}"

    covering_ids = {
        c.chunk_id
        for doc_id, quote in M07_SPANS
        for c in covering_chunks(improved_chunks, corpus, doc_id, quote)
    }
    assert len(covering_ids) == 3, (
        "the three M-07 spans must live in three distinct chunks; if they collapse "
        "into fewer, the case stops testing multi-hop retrieval"
    )


# ---------------------------------------------------------------------------
# A-08 -- a fix that worked at the chunk level and did NOT fix the case
# ---------------------------------------------------------------------------

A08_SPANS = [
    ("data-retention", "| Transaction records | **7 years** |"),
    ("data-retention", "| **Webhook delivery logs** | **30 days** |"),
]


def test_a08_retention_table_is_atomic_under_improved_chunking_but_the_case_still_failed(
    corpus: Corpus, baseline_chunks: list[Chunk], improved_chunks: list[Chunk]
) -> None:
    """A-08: "Of everything NovaPay stores, what is kept longest and what is kept
    shortest?"

    Originating dev case: A-08 (aggregation).
    Original failure class: retrieval_miss -- and it was STILL retrieval_miss in
    the improved run. Baseline recall@5 0.000, improved recall@5 0.000.

    Why this assertion is meaningful, and why a passing test here is not a
    success story. `configs/improved.yaml` names A-08 as motivating structure-
    aware chunking: the fixed chunker cut the retention table in half so the
    longest and shortest values landed in different chunks. That chunk-level
    problem WAS fixed -- the table is covered by two chunks under fixed-size
    chunking and one under structure-aware chunking. The case failed anyway.

    Freezing it is the point. Without this test the chunk-level improvement and
    the case-level outcome blur together, and "structure-aware chunking fixed the
    A-08 problem" becomes sayable. It did not. It fixed the mechanism it was
    aimed at and the case still failed, which is a more useful thing to know.

    Which intervention preserves it: intervention 1, structure-aware chunking,
    treating a Markdown table as atomic.
    """
    baseline_covering = {
        c.chunk_id for doc, q in A08_SPANS for c in covering_chunks(baseline_chunks, corpus, doc, q)
    }
    improved_covering = {
        c.chunk_id for doc, q in A08_SPANS for c in covering_chunks(improved_chunks, corpus, doc, q)
    }

    assert len(baseline_covering) == 2, (
        "the premise of this test is that fixed-size chunking splits the retention "
        "table across two chunks; it no longer does"
    )
    assert len(improved_covering) == 1, (
        "REGRESSION: the retention table is no longer atomic under structure-aware "
        "chunking, so the longest and shortest retention values are again in "
        "different chunks"
    )


# ---------------------------------------------------------------------------
# Lexical retrieval on exact tokens -- MECHANISM test, not a frozen failure
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("token", "expected_doc"),
    [
        ("PAY_003", "api-authentication"),
        ("NovaPay-Signature", "webhook-delivery"),
        ("sk_live_", "api-authentication"),
    ],
)
def test_exact_rare_tokens_are_retrieved_at_rank_one_by_the_lexical_member(
    corpus: Corpus, improved_chunks: list[Chunk], token: str, expected_doc: str
) -> None:
    """Exact identifiers must be findable by the token itself.

    NOT derived from a confirmed dev failure, and labelled as such deliberately.
    No dev case asks about an error code or an API key prefix, so there is no
    measured failure to freeze here. What this protects is the RATIONALE for
    intervention 2 (hybrid dense + BM25 fusion): an embedding model maps
    `PAY_003` and `PAY_004` to nearly the same vector, because they differ by one
    character in a position dense retrieval has no reason to care about. Lexical
    matching is what distinguishes them.

    Freezing it now means that if the corpus later grows error-code questions,
    the capability they depend on is already under test rather than assumed. It
    also fails loudly if the tokeniser is ever changed to one that splits on
    underscores or hyphens, which would silently destroy this property -- the
    regex in retrievers.py exists precisely to prevent that.
    """
    retriever = BM25Retriever(improved_chunks)
    results = retriever.retrieve(token, 3)

    assert results, f"BM25 returned nothing for {token!r}"
    top = results[0]
    assert token in top.chunk.text, (
        f"REGRESSION: the top BM25 result for the exact token {token!r} does not "
        f"contain it. Check the tokeniser in retrievers.py -- a \\w+ split would "
        f"break {token!r} into pieces that match everything and mean nothing."
    )
    assert top.chunk.doc_id == expected_doc
    assert top.score > 0.0


def test_a_rare_token_survives_chunking_intact(
    corpus: Corpus, improved_chunks: list[Chunk]
) -> None:
    """A token split across a chunk boundary cannot be matched by any retriever."""
    for token in ("PAY_003", "NovaPay-Signature", "sk_live_"):
        assert any(token in c.text for c in improved_chunks), (
            f"REGRESSION: {token!r} does not appear intact in any chunk"
        )


# ---------------------------------------------------------------------------
# Citation resolution
# ---------------------------------------------------------------------------


def test_no_confirmed_citation_resolution_failure_exists_to_freeze() -> None:
    """Documented absence, so the gap is visible rather than merely unfilled.

    The Phase-4 brief asked for a frozen citation-resolution failure "if an
    appropriate one exists". None does. `citation_validity` is 1.000 in all four
    frozen runs with a paired-bootstrap interval of exactly [0.000, 0.000]: no
    pipeline has ever emitted a label that failed to resolve, on either split.

    That is a real property of binding citations to the context map rather than
    to a second retrieval pass -- and it also means the metric has no headroom
    and cannot distinguish the two arms. The capability is instead tested
    constructively in tests/integration/test_pipeline_end_to_end.py, where the
    fixture answer for FX-02 cites [C9] against a three-chunk context and the
    binder is required to record it as fabricated rather than drop it.

    This test asserts nothing about the pipeline. It exists so that the absence
    is stated in the suite rather than inferred from a missing file.
    """
    assert True
