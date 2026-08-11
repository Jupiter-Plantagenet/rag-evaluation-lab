"""Retriever behaviour and the properties the comparison depends on.

Uses TfidfSvdEmbedder throughout so the whole file runs offline with no model
download -- the same backend CI uses.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from rag_eval.ingest.chunkers import MarkdownStructureChunker
from rag_eval.ingest.corpus import load_corpus
from rag_eval.retrieval.embedders import TfidfSvdEmbedder
from rag_eval.retrieval.retrievers import (
    BM25Retriever,
    DenseRetriever,
    ReciprocalRankFusionRetriever,
    deduplicate_by_overlap,
    tokenize,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "data" / "corpus" / "novapay"


@pytest.fixture(scope="module")
def chunks():
    corpus = load_corpus(CORPUS_DIR)
    chunker = MarkdownStructureChunker()
    return [c for doc in corpus.documents.values() for c in chunker.chunk(doc)]


@pytest.fixture(scope="module")
def dense(chunks):
    embedder = TfidfSvdEmbedder(dimension=128).fit([c.text for c in chunks])
    matrix = embedder.encode([c.text for c in chunks])
    return DenseRetriever(chunks, matrix, embedder)


@pytest.fixture(scope="module")
def bm25(chunks):
    return BM25Retriever(chunks)


# --- tokenizer ---------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "text,expected",
    [
        ("2.9% + $0.30", ["2.9%", "0.30"]),
        ("Use sk_live_ keys", ["sk_live_", "keys"]),
        ("Error PAY_003 means", ["pay_003", "means"]),
    ],
)
def test_tokenizer_keeps_domain_tokens_intact(text, expected) -> None:
    """Splitting a number from its unit destroys the thing being matched."""
    tokens = tokenize(text)
    for e in expected:
        assert any(e in t for t in tokens), f"{e!r} lost from {tokens}"


@pytest.mark.unit
def test_stoplist_preserves_negation() -> None:
    """ "no" and "not" must survive: grounding depends on them.

    A standard stoplist removes both, which would make "no refund fee" and
    "refund fee" identical to the lexical retriever and to the groundedness
    checker that shares this tokenizer.
    """
    tokens = tokenize("There is no fee and it is not available")
    assert "no" in tokens
    assert "not" in tokens


# --- ranking properties ------------------------------------------------------


@pytest.mark.unit
def test_dense_retrieval_is_deterministic(dense) -> None:
    a = [s.chunk.chunk_id for s in dense.retrieve("what are the card fees?", 8)]
    b = [s.chunk.chunk_id for s in dense.retrieve("what are the card fees?", 8)]
    assert a == b


@pytest.mark.unit
def test_ranks_are_contiguous_from_one(dense, bm25) -> None:
    """Metrics are computed from rank; a gap would silently distort MRR."""
    for retriever in (dense, bm25):
        results = retriever.retrieve("payout schedule", 6)
        assert [s.rank for s in results] == list(range(1, len(results) + 1))


@pytest.mark.unit
def test_bm25_finds_exact_identifiers_that_dense_retrieval_blurs(dense, bm25) -> None:
    """The reason hybrid retrieval is on the intervention list at all.

    An embedding model maps PAY_003 to roughly where it maps every other
    alphanumeric token; BM25 treats it as the rare term it is.
    """
    lexical = [s.chunk.chunk_id for s in bm25.retrieve("PAY_003", 5)]
    hits = [
        cid
        for cid in lexical
        if "PAY_003"
        in next(s.chunk.text for s in bm25.retrieve("PAY_003", 5) if s.chunk.chunk_id == cid)
    ]
    assert hits, "BM25 should surface the chunk literally containing PAY_003"


@pytest.mark.unit
def test_rrf_is_invariant_to_member_score_scale(chunks, dense) -> None:
    """The property that makes fusion safe without a tuned normalisation.

    If fusion depended on score magnitude, the weighting would have to be fitted
    on the dev set -- turning a "no tuning" claim into a false one.
    """

    class Scaled:
        name = "dense"

        def __init__(self, inner, factor):
            self.inner = inner
            self.factor = factor

        def retrieve(self, query, k):
            import dataclasses

            return [
                dataclasses.replace(s, score=s.score * self.factor)
                for s in self.inner.retrieve(query, k)
            ]

    normal = ReciprocalRankFusionRetriever([dense, BM25Retriever(chunks)])
    scaled = ReciprocalRankFusionRetriever([Scaled(dense, 1000.0), BM25Retriever(chunks)])

    q = "how long do payouts take?"
    assert [s.chunk.chunk_id for s in normal.retrieve(q, 8)] == [
        s.chunk.chunk_id for s in scaled.retrieve(q, 8)
    ]


@pytest.mark.unit
def test_rrf_output_is_a_permutation_of_member_results(chunks, dense) -> None:
    """Fusion may reorder and truncate, never invent."""
    bm = BM25Retriever(chunks)
    fused = ReciprocalRankFusionRetriever([dense, bm], fetch_k=20)
    q = "dispute fee"
    allowed = {s.chunk.chunk_id for s in dense.retrieve(q, 20)} | {
        s.chunk.chunk_id for s in bm.retrieve(q, 20)
    }
    assert {s.chunk.chunk_id for s in fused.retrieve(q, 10)} <= allowed


@pytest.mark.unit
def test_rrf_score_matches_the_published_formula(chunks, dense) -> None:
    """1/(60+rank) summed across members, used as published rather than tuned."""
    bm = BM25Retriever(chunks)
    fused = ReciprocalRankFusionRetriever([dense, bm], k_rrf=60, fetch_k=30)
    q = "refund window"

    ranks: dict[str, list[int]] = {}
    for member in (dense, bm):
        for s in member.retrieve(q, 30):
            ranks.setdefault(s.chunk.chunk_id, []).append(s.rank)

    for s in fused.retrieve(q, 5):
        expected = sum(1.0 / (60 + r) for r in ranks[s.chunk.chunk_id])
        assert s.rrf_score == pytest.approx(expected, rel=1e-9)


@pytest.mark.unit
def test_deduplication_renumbers_ranks(chunks, dense) -> None:
    results = dense.retrieve("fees", 10)
    deduped = deduplicate_by_overlap(results)
    assert [s.rank for s in deduped] == list(range(1, len(deduped) + 1))
    assert len(deduped) <= len(results)


@pytest.mark.unit
def test_embedder_fingerprint_changes_with_configuration(chunks) -> None:
    """Cache keys include this. If it collided, vectors from one model would be
    silently reused for another and every retrieval number would be wrong."""
    texts = [c.text for c in chunks]
    a = TfidfSvdEmbedder(dimension=64).fit(texts).fingerprint()
    b = TfidfSvdEmbedder(dimension=128).fit(texts).fingerprint()
    c = TfidfSvdEmbedder(dimension=64, seed=99).fit(texts).fingerprint()
    assert len({a, b, c}) == 3


@pytest.mark.unit
def test_embeddings_are_unit_normalised(chunks) -> None:
    """Cosine similarity is computed as a dot product, which assumes this."""
    embedder = TfidfSvdEmbedder(dimension=64).fit([c.text for c in chunks])
    vectors = embedder.encode([c.text for c in chunks[:20]])
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)
