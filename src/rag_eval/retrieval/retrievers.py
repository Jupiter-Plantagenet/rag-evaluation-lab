"""Retrievers: dense, lexical, and their fusion.

Kept in one module because dense and lexical retrieval must share a tokenizer
with the groundedness checker. Splitting them across files is how the two halves
of a system silently desynchronise -- a change to normalisation on one side
alters retrieval without altering grounding, and the resulting metric shift gets
attributed to whatever else changed that week.

BM25 is implemented here rather than taken from ``rank_bm25`` for the same
reason: the dependency would bring its own tokenizer, and then "the same words"
would mean two different things in one pipeline.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol

import numpy as np

from rag_eval.types import Chunk, ScoredChunk

# Matches an optional leading currency symbol, an alphanumeric core that may
# contain underscores, any number of internal .-+/ separated groups, and an
# optional trailing percent sign. That covers the token shapes this corpus turns
# on -- $0.30, 2.9%, T+2, PAY_003, sk_live_, NovaPay-Signature -- each of which a
# naive \w+ splits into pieces that match everything and mean nothing.
TOKEN_RE = re.compile(r"\$?[a-z0-9_]+(?:[.\-+/][a-z0-9_]+)*%?")

# Kept deliberately short. An aggressive stoplist strips tokens that carry real
# meaning in this corpus -- "no fee", "not available", "up to" -- and negation is
# exactly where a grounding checker must not lose information.
STOPWORDS = frozenset(
    "a an the of to in for on at by is are was were be been it its this that "
    "as with from or and if then than which what when how".split()
)


def tokenize(text: str) -> list[str]:
    """One tokenizer, shared by BM25 and the groundedness cascade.

    Keeps ``2.9%``, ``$0.30``, ``T+2`` and ``sk_live_`` as single tokens: in a
    corpus about fees and limits, splitting a number from its unit destroys the
    thing being matched.
    """
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


class Retriever(Protocol):
    name: str

    def retrieve(self, query: str, k: int) -> list[ScoredChunk]: ...


class DenseRetriever:
    """Exact cosine search over L2-normalised vectors.

    Brute force, via a single matrix product. At this corpus size an approximate
    index would add a second source of non-determinism (build order, thread
    count) for no measurable speed benefit, and the point of the project is that
    numbers reproduce.
    """

    name = "dense"

    def __init__(self, chunks: list[Chunk], matrix: np.ndarray, embedder) -> None:
        if len(chunks) != matrix.shape[0]:
            raise ValueError(f"{len(chunks)} chunks but {matrix.shape[0]} vectors")
        self.chunks = chunks
        self.matrix = matrix
        self.embedder = embedder

    def retrieve(self, query: str, k: int) -> list[ScoredChunk]:
        qv = self.embedder.encode([query], is_query=True)
        scores = (self.matrix @ qv[0]).astype(np.float64)

        # Stable ordering: ties broken by chunk_id, never by array order, so two
        # runs on identical data produce identical rankings.
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], self.chunks[i].chunk_id))
        return [
            ScoredChunk(
                chunk=self.chunks[i],
                rank=rank + 1,
                score=float(scores[i]),
                dense_score=float(scores[i]),
            )
            for rank, i in enumerate(order[:k])
        ]


class BM25Retriever:
    """Okapi BM25 over the shared tokenizer.

    Present because dense retrieval systematically misses exact identifiers --
    ``PAY_003``, ``sk_live_``, ``NovaPay-Signature``. Those are precisely the
    tokens a developer searches for, and an embedding model maps them to
    roughly the same place as every other alphanumeric string.
    """

    name = "bm25"

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.docs = [tokenize(c.text) for c in chunks]
        self.doc_len = [len(d) for d in self.docs]
        self.avgdl = (sum(self.doc_len) / len(self.docs)) if self.docs else 0.0
        self.tf = [Counter(d) for d in self.docs]

        df: Counter[str] = Counter()
        for doc in self.docs:
            df.update(set(doc))
        n = len(self.docs)
        # Robertson/Sparck-Jones IDF with the +1 that keeps it non-negative: the
        # raw form goes negative for terms in more than half the documents,
        # which in a 14-document corpus would make common words actively
        # penalise a chunk.
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def retrieve(self, query: str, k: int) -> list[ScoredChunk]:
        q_tokens = tokenize(query)
        scores = np.zeros(len(self.docs), dtype=np.float64)
        for i, tf in enumerate(self.tf):
            dl = self.doc_len[i]
            total = 0.0
            for t in q_tokens:
                f = tf.get(t, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1e-9))
                total += self.idf.get(t, 0.0) * f * (self.k1 + 1) / denom
            scores[i] = total

        order = sorted(range(len(scores)), key=lambda i: (-scores[i], self.chunks[i].chunk_id))
        return [
            ScoredChunk(
                chunk=self.chunks[i],
                rank=rank + 1,
                score=float(scores[i]),
                lexical_score=float(scores[i]),
            )
            for rank, i in enumerate(order[:k])
        ]


class ReciprocalRankFusionRetriever:
    """Fuse rankings by reciprocal rank, not by score.

    Dense cosine lives in [-1, 1]; BM25 is unbounded and corpus-dependent. Any
    weighted sum of the two requires a normalisation that is itself a tuned
    parameter, and that parameter would be fitted on the dev set -- quietly
    turning a "no tuning" claim into a false one.

    RRF uses only rank, so it needs no normalisation and no per-corpus fitting.
    ``score = sum over retrievers of 1 / (k_rrf + rank)``, with ``k_rrf = 60``
    from Cormack et al. (2009), used as published rather than tuned here.
    """

    name = "hybrid_rrf"

    def __init__(self, members: list[Retriever], k_rrf: int = 60, fetch_k: int = 30) -> None:
        self.members = members
        self.k_rrf = k_rrf
        self.fetch_k = fetch_k

    def retrieve(self, query: str, k: int) -> list[ScoredChunk]:
        fused: dict[str, float] = {}
        seen: dict[str, Chunk] = {}
        per_member: dict[str, dict[str, float]] = {}

        for member in self.members:
            results = member.retrieve(query, self.fetch_k)
            per_member[member.name] = {}
            for sc in results:
                cid = sc.chunk.chunk_id
                seen[cid] = sc.chunk
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (self.k_rrf + sc.rank)
                per_member[member.name][cid] = sc.score

        order = sorted(fused, key=lambda cid: (-fused[cid], cid))
        return [
            ScoredChunk(
                chunk=seen[cid],
                rank=rank + 1,
                score=fused[cid],
                rrf_score=fused[cid],
                dense_score=per_member.get("dense", {}).get(cid),
                lexical_score=per_member.get("bm25", {}).get(cid),
            )
            for rank, cid in enumerate(order[:k])
        ]


def deduplicate_by_overlap(results: list[ScoredChunk], max_overlap: float = 0.8) -> list[ScoredChunk]:
    """Drop lower-ranked chunks that mostly repeat a higher-ranked one.

    Overlapping chunkers emit near-duplicates, and feeding three copies of the
    same passage to the model wastes context budget while making the answer look
    better corroborated than the evidence warrants.

    Ranks are RENUMBERED after removal, because retrieval metrics are computed
    from rank and a gap would silently distort MRR.
    """
    kept: list[ScoredChunk] = []
    for sc in results:
        tokens = set(tokenize(sc.chunk.text))
        if not tokens:
            continue
        duplicate = False
        for k in kept:
            other = set(tokenize(k.chunk.text))
            if other and len(tokens & other) / min(len(tokens), len(other)) >= max_overlap:
                duplicate = True
                break
        if not duplicate:
            kept.append(sc)

    return [
        ScoredChunk(
            chunk=sc.chunk,
            rank=i + 1,
            score=sc.score,
            dense_score=sc.dense_score,
            lexical_score=sc.lexical_score,
            rrf_score=sc.rrf_score,
            rerank_score=sc.rerank_score,
            rank_before_rerank=sc.rank,
        )
        for i, sc in enumerate(kept)
    ]
