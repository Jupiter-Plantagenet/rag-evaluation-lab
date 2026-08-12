"""Pipeline assembly.

Baseline and improved are the SAME class with different configuration. There is
no ``if variant == "improved"`` anywhere, and a test asserts as much.

That constraint is methodological, not stylistic. If the two pipelines were
separate code paths, a measured difference between them could always be an
artefact of an unrelated difference in their implementations, and the comparison
would establish nothing about the interventions. Sharing one path means the
config diff *is* the experimental manipulation.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from jinja2 import Template
from numpy.typing import NDArray

from rag_eval.citation.link import (
    bind_citations,
    detect_abstention,
    detect_clarification,
    split_claims,
)
from rag_eval.config import PipelineConfig
from rag_eval.errors import ConfigError
from rag_eval.generation.cache import DiskCache, cache_root
from rag_eval.generation.generators import CachedGenerator, build_generator
from rag_eval.ingest.chunkers import build_chunker
from rag_eval.ingest.corpus import Corpus, load_corpus
from rag_eval.retrieval.embedders import Embedder, TfidfSvdEmbedder, build_embedder
from rag_eval.retrieval.retrievers import (
    BM25Retriever,
    DenseRetriever,
    ReciprocalRankFusionRetriever,
    deduplicate_by_overlap,
)
from rag_eval.types import Chunk, PipelineOutput, ScoredChunk

PROMPT_DIR = Path(__file__).parent / "generation" / "prompts"


def _template_sha(path: Path) -> str:
    """Hash of the prompt SOURCE, folded into every cache key.

    Without it, editing the prompt would silently reuse answers generated from
    different instructions -- the most insidious possible cache bug, because
    everything still runs and the numbers merely become meaningless.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def pack_context(results: list[ScoredChunk]) -> tuple[str, dict[str, str]]:
    """Render retrieved chunks as labelled excerpts.

    Returns the context string and the ``{"C1": chunk_id}`` map. That map is
    the binding contract: citations resolve against it, so a citation can only
    ever point at something the model was actually shown.
    """
    parts: list[str] = []
    labels: dict[str, str] = {}
    for i, sc in enumerate(results, start=1):
        label = f"C{i}"
        labels[label] = sc.chunk.chunk_id
        heading = " > ".join(sc.chunk.heading_path) if sc.chunk.heading_path else sc.chunk.doc_id
        parts.append(f"[{label}] ({sc.chunk.doc_id} :: {heading})\n{sc.chunk.text.strip()}")
    return "\n\n".join(parts), labels


@dataclass
class Pipeline:
    config: PipelineConfig
    corpus: Corpus
    chunks: list[Chunk]
    retriever: object
    generator: object
    template: Template
    template_sha: str

    @property
    def name(self) -> str:
        return self.config.name

    def answer(self, question: str) -> PipelineOutput:
        started = time.perf_counter()
        errors: list[str] = []

        results = self.retriever.retrieve(question, self.config.retrieval.top_k)  # type: ignore[attr-defined]
        if self.config.retrieval.deduplicate:
            results = deduplicate_by_overlap(results, self.config.retrieval.dedupe_threshold)

        context_text, labels = pack_context(results)
        prompt = self.template.render(context=context_text, question=question)

        completion = self.generator.generate(prompt, template_sha=self.template_sha)  # type: ignore[attr-defined]
        answer = completion.text

        claims = split_claims(answer)
        citations, unresolved = bind_citations(
            claims,
            labels,
            results,
            self.corpus.bodies(),
        )

        return PipelineOutput(
            query=question,
            answer=answer,
            retrieved=tuple(results),
            context_text=context_text,
            context_labels=labels,
            raw_prompt=completion.raw_prompt,
            claims=tuple(claims),
            citations=tuple(citations),
            abstained=detect_abstention(answer),
            clarification_requested=detect_clarification(answer),
            usage=completion.usage,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            cache_hit=completion.cache_hit,
            unresolved_labels=tuple(unresolved),
            errors=tuple(errors),
        )


def build_pipeline(config: PipelineConfig, corpus_dir: Path) -> Pipeline:
    """Assemble a pipeline from configuration alone.

    Every branch below is on a config VALUE, never on a variant name. Adding an
    ``if config.name == "improved"`` here would break the comparison's validity,
    and ``test_pipelines_differ_only_by_config`` fails if one appears.
    """
    corpus = load_corpus(corpus_dir)

    chunker = build_chunker(config.chunker.kind, **config.chunker.params)
    chunks = [c for doc in corpus.documents.values() for c in chunker.chunk(doc)]
    if not chunks:
        raise ConfigError("chunking produced no chunks")

    embedder = build_embedder(config.embedder.kind, **config.embedder.params)
    if isinstance(embedder, TfidfSvdEmbedder):
        embedder.fit([c.text for c in chunks])

    matrix = _embed_chunks(embedder, chunks)
    dense = DenseRetriever(chunks, matrix, embedder)

    kind = config.retrieval.kind
    if kind == "dense":
        retriever: object = dense
    elif kind == "bm25":
        retriever = BM25Retriever(chunks)
    elif kind == "hybrid_rrf":
        retriever = ReciprocalRankFusionRetriever(
            [dense, BM25Retriever(chunks)],
            k_rrf=config.retrieval.k_rrf,
            fetch_k=config.retrieval.fetch_k,
        )
    else:
        raise ConfigError(f"unknown retrieval kind: {kind!r}")

    generator = CachedGenerator(
        build_generator(config.generator.kind, **config.generator.params),
        DiskCache(cache_root(), "llm"),
    )

    prompt_path = PROMPT_DIR / config.generator.prompt_template
    if not prompt_path.exists():
        raise ConfigError(f"prompt template not found: {prompt_path}")

    return Pipeline(
        config=config,
        corpus=corpus,
        chunks=chunks,
        retriever=retriever,
        generator=generator,
        template=Template(prompt_path.read_text(encoding="utf-8")),
        template_sha=_template_sha(prompt_path),
    )


def _embed_chunks(embedder: Embedder, chunks: list[Chunk]) -> NDArray[np.float32]:
    """Embed the corpus, caching by (embedder fingerprint, chunk text).

    Cached per text rather than per batch, so changing top-k, the chunk ordering,
    or the retriever never re-embeds anything.
    """
    from rag_eval.generation.cache import DiskCache, stable_hash

    cache = DiskCache(cache_root(), "embeddings")
    fp = embedder.fingerprint()

    vectors: list[NDArray[np.float32]] = []
    missing: list[tuple[int, str]] = []
    for i, chunk in enumerate(chunks):
        key = stable_hash({"fp": fp, "text": chunk.text})
        record = cache.get(key)
        if record is None:
            vectors.append(np.zeros(embedder.dimension, dtype=np.float32))
            missing.append((i, key))
        else:
            vectors.append(np.asarray(record["vector"], dtype=np.float32))

    if missing:
        encoded = embedder.encode([chunks[i].text for i, _ in missing])
        for (i, key), vector in zip(missing, encoded, strict=True):
            vectors[i] = vector
            cache.put(key, {"vector": [float(x) for x in vector]})

    return np.vstack(vectors)
