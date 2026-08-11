"""Shared fixtures for the frozen-failure regression suite.

These tests run against the REAL NovaPay corpus, because a regression test built
on a synthetic stand-in would not detect the thing it exists to detect: a corpus
edit or a chunker change that quietly re-breaks a case that was measured as
fixed.

They are deliberately embedder-independent wherever possible. The frozen runs
used MiniLM, which CI does not install; asserting on chunk structure and on BM25
(which needs no embedding at all) means these tests check the mechanism that was
credited with the fix rather than a ranking that cannot be reproduced offline.
Where a dense retriever is unavoidable the config uses `tfidf_svd`, and the
assertion is coarse enough to be robust to the substitution -- and says so.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rag_eval.data.spans import resolve_quote
from rag_eval.ingest.chunkers import build_chunker
from rag_eval.ingest.corpus import Corpus, load_corpus
from rag_eval.types import Chunk

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "data" / "corpus" / "novapay"

# The two chunker configurations under comparison, copied from configs/. The
# baseline is the one the frozen baseline run used; the improved is intervention
# 1 in configs/improved.yaml.
BASELINE_CHUNKER = ("fixed_size", {"chunk_size": 500, "chunk_overlap": 50})
IMPROVED_CHUNKER = (
    "markdown_structure",
    {"chunk_size": 500, "chunk_overlap": 50, "max_chars": 1200, "min_chars": 120},
)

HIT_THRESHOLD = 0.5


@pytest.fixture(scope="session")
def corpus() -> Corpus:
    return load_corpus(CORPUS_DIR)


def chunk_corpus(corpus: Corpus, which: tuple[str, dict[str, object]]) -> list[Chunk]:
    kind, params = which
    chunker = build_chunker(kind, **params)
    return [c for doc in corpus.documents.values() for c in chunker.chunk(doc)]


@pytest.fixture(scope="session")
def baseline_chunks(corpus: Corpus) -> list[Chunk]:
    return chunk_corpus(corpus, BASELINE_CHUNKER)


@pytest.fixture(scope="session")
def improved_chunks(corpus: Corpus) -> list[Chunk]:
    return chunk_corpus(corpus, IMPROVED_CHUNKER)


def covering_chunks(chunks: list[Chunk], corpus: Corpus, doc_id: str, quote: str) -> list[Chunk]:
    """Chunks whose span covers the evidence quote, by the project's own rule."""
    from rag_eval.data.spans import is_hit

    body = corpus[doc_id].body
    located = resolve_quote(body, quote)
    assert located is not None, (
        f"the evidence quote no longer resolves in {doc_id}:\n  {quote!r}\n"
        "The corpus was edited. Ground truth is derived from this quote, so the "
        "case it belongs to can no longer be scored."
    )
    return [
        c
        for c in chunks
        if c.doc_id == doc_id
        and is_hit(located, (c.char_start, c.char_end), threshold=HIT_THRESHOLD)
    ]
