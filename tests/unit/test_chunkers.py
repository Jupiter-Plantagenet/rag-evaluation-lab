"""Chunker invariants.

The offset invariant is the important one. Everything downstream -- citation
resolution, retrieval scoring against evidence spans, the source-span viewer --
assumes `doc.body[c.char_start:c.char_end] == c.text`. If that ever stops
holding, nothing crashes; citations simply start pointing at the wrong text, and
the metrics keep reporting numbers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rag_eval.ingest.chunkers import FixedSizeChunker, MarkdownStructureChunker, build_chunker
from rag_eval.ingest.corpus import load_corpus

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "data" / "corpus" / "novapay"

CHUNKERS = [
    FixedSizeChunker(chunk_size=500, chunk_overlap=50),
    MarkdownStructureChunker(max_chars=1200, min_chars=120),
]


@pytest.fixture(scope="module")
def corpus():
    return load_corpus(CORPUS_DIR)


@pytest.mark.unit
@pytest.mark.parametrize("chunker", CHUNKERS, ids=lambda c: c.name)
def test_offsets_reconstruct_the_source_exactly(chunker, corpus) -> None:
    """The invariant every citation depends on."""
    for doc in corpus.documents.values():
        for chunk in chunker.chunk(doc):
            assert doc.body[chunk.char_start : chunk.char_end] == chunk.text, (
                f"{chunk.chunk_id}: offsets do not reconstruct the text. "
                f"Every citation into this chunk would resolve to the wrong span."
            )


@pytest.mark.unit
@pytest.mark.parametrize("chunker", CHUNKERS, ids=lambda c: c.name)
def test_chunk_ids_are_stable_across_rebuilds(chunker, corpus) -> None:
    """Content-addressed, so two runs are comparable at chunk level.

    The predecessor project used random UUID4 docstore keys, which changed on
    every rebuild -- making it impossible to say whether two runs retrieved the
    same evidence.
    """
    first = {c.chunk_id for doc in corpus.documents.values() for c in chunker.chunk(doc)}
    second = {c.chunk_id for doc in corpus.documents.values() for c in chunker.chunk(doc)}
    assert first == second


@pytest.mark.unit
@pytest.mark.parametrize("chunker", CHUNKERS, ids=lambda c: c.name)
def test_chunks_cover_all_substantive_text(chunker, corpus) -> None:
    """No document content may be unreachable by retrieval.

    A gap in coverage produces a question that is answerable in principle and
    unanswerable in practice, which would be scored as a retrieval failure
    while actually being an ingestion bug.
    """
    for doc in corpus.documents.values():
        covered = bytearray(len(doc.body))
        for chunk in chunker.chunk(doc):
            for i in range(chunk.char_start, chunk.char_end):
                covered[i] = 1
        missed = "".join(ch for i, ch in enumerate(doc.body) if not covered[i])
        assert not missed.strip(), f"{doc.doc_id}: uncovered text {missed.strip()[:120]!r}"


@pytest.mark.unit
def test_structure_chunker_keeps_headings_with_their_content(corpus) -> None:
    """The property the fixed-size chunker cannot provide."""
    chunker = MarkdownStructureChunker()
    doc = corpus["payout-schedules"]
    chunks = chunker.chunk(doc)

    assert all(c.heading_path for c in chunks), "every structured chunk should know its section"

    express = [c for c in chunks if any("Express" in h for h in c.heading_path)]
    assert express, "the Express payouts section should be identifiable by heading"
    assert any("0.5%" in c.text for c in express), (
        "the express payout fee must live in a chunk that knows it is about express payouts"
    )


@pytest.mark.unit
def test_structure_chunker_does_not_orphan_table_rows(corpus) -> None:
    """A table cell without its header row is unanswerable data.

    F-15 ("how many dashboard seats on Pro?") depends on this: the value 15 is
    meaningful only by column position, so a chunk holding the row without the
    header cannot answer the question even when retrieval works perfectly.
    """
    chunker = MarkdownStructureChunker()
    doc = corpus["subscription-plans"]
    seat_chunks = [c for c in chunker.chunk(doc) if "Dashboard seats" in c.text]
    assert seat_chunks, "the seats row should exist in some chunk"
    for c in seat_chunks:
        assert "Starter" in c.text and "Pro" in c.text, (
            "the seats row was separated from its table header, so the value 15 "
            "cannot be attributed to a plan"
        )


@pytest.mark.unit
def test_fixed_size_chunker_is_simple_not_broken(corpus) -> None:
    """The baseline must be a fair comparator.

    An intentionally crippled baseline would make the improvement meaningless.
    These assertions check it produces sane, non-degenerate chunks.
    """
    chunker = FixedSizeChunker(chunk_size=500, chunk_overlap=50)
    chunks = [c for doc in corpus.documents.values() for c in chunker.chunk(doc)]

    assert len(chunks) > 100, "the corpus should yield a workable number of chunks"
    assert all(c.text.strip() for c in chunks), "no empty chunks"
    assert all(len(c.text) <= 500 for c in chunks)
    assert sum(len(c.text) for c in chunks) / len(chunks) > 200, "chunks should not be tiny"


@pytest.mark.unit
def test_corpus_yields_enough_chunks_for_top_k_to_discriminate(corpus) -> None:
    """Guards the defect that motivated the whole project.

    The predecessor corpus produced 11 chunks, so top-k=4 returned 36% of it for
    any query and retrieval metrics were saturated by construction. With k=4,
    100+ chunks means a hit is informative.
    """
    for chunker in CHUNKERS:
        n = sum(len(chunker.chunk(doc)) for doc in corpus.documents.values())
        assert n >= 60, f"{chunker.name} produced only {n} chunks; retrieval would be too easy"


@pytest.mark.unit
def test_build_chunker_rejects_unknown_kinds() -> None:
    with pytest.raises(ValueError, match="unknown chunker"):
        build_chunker("semantic_magic")


@pytest.mark.unit
def test_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValueError):
        FixedSizeChunker(chunk_size=100, chunk_overlap=100)
