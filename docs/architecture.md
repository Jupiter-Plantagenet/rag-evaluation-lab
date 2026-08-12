# Architecture

The deliverable is an evaluation harness, not a chatbot. The system under test is
deliberately ordinary; the apparatus around it is the work.

## Shape

```
data/corpus/novapay/*.md          14 synthetic documents + fact_ledger.yaml
data/eval/novapay_v1.yaml         50 cases, dev 28 / test 22
        |
        v
  ingest/corpus.py        load documents, hash them, expose bodies
  ingest/chunkers.py      fixed_size | markdown_structure  -> Chunk(char_start, char_end)
        |
        v
  retrieval/embedders.py  minilm | tfidf_svd | gemini      -> normalised vectors
  retrieval/retrievers.py dense | bm25 | hybrid_rrf        -> ScoredChunk(rank, scores)
        |
        v
  pipeline.py             pack_context -> {"C1": chunk_id}, render prompt
  generation/generators.py gemini | scripted, wrapped in CachedGenerator
        |
        v
  citation/link.py        split_claims -> bind_citations against the SAME context map
        |
        v
  tracing/schema.py       one TraceRecord per case -> trace.jsonl
        |
        v
  evaluation/metrics.py   deterministic scores, pure functions of the trace
  evaluation/taxonomy.py  ordered failure classification
  reporting/compare.py    paired bootstrap -> comparison.{json,md,csv}
```

## The five decisions that carry the design

### 1. One pipeline class, two configurations

`build_pipeline` branches on config **values** only. There is no
`if variant == "improved"` anywhere, and an integration test asserts that two
configs differing only in retrieval settings produce different `pipeline_hash`
values while two differing only by label do not.

This is methodological, not stylistic. If the arms were separate code paths, any
measured difference could be an artefact of an unrelated implementation
difference, and the comparison would establish nothing. Sharing one path makes the
config diff *be* the experimental manipulation.

### 2. Chunks carry character offsets into their source document

`Chunk.char_start` / `char_end` index the parent `Document.body`. Without them a
citation can only name a chunk id, which means nothing to a reader and nothing
across chunking configurations. This is the single property whose absence made the
predecessor project's citations unresolvable.

Corpus bodies are NFC-normalised and otherwise untouched. Ground-truth evidence
offsets are derived from quotes at load time and index exactly those characters,
so any further normalisation would shift every span in the dataset by a
document-dependent amount.

### 3. Citations bind to the context map, not to a second retrieval pass

`pack_context` returns both the context string and `{"C1": chunk_id}`.
`bind_citations` resolves labels against **that map**. The citation and the
evidence therefore cannot disagree.

The predecessor displayed sources from a *different* retrieval call than the one
that fed the model; they agreed only by coincidence. A label with no entry in the
map is recorded with `resolved=False` — a fabricated citation, counted rather than
dropped, because dropping it reports zero.

Claim segmentation is rule-based. An LLM claim-splitter would put a model inside
the measurement of that model's own grounding, and an atomiser that quietly merges
two assertions makes an ungrounded one disappear.

### 4. Running and scoring are separate

The runner writes traces; metrics are pure functions of a stored trace. A metric
definition can be corrected afterwards and the whole experiment re-scored with no
model calls. If scoring happened inline and only aggregates survived, every
definition change would cost a full re-run — and at 5 requests/minute on a free
tier, that cost is what makes people quietly not fix definitions.

A failing case still produces a trace: exceptions are caught, recorded in
`errors`, and the run continues. A run that aborts at case 8 of 28 tells you
nothing about cases 9–28, and the temptation is then to exclude the failure.

### 5. The cache is content-addressed and never expires

`llm_cache_key` covers provider, model, generation params, the prompt, and the
**prompt template hash**. Editing a prompt therefore invalidates its entries
rather than silently reusing answers generated from different instructions. There
is no TTL: a research cache that expires on a timer destroys reproducibility on a
timer.

On a cache miss while offline the pipeline **raises**. CI integration tests use
deterministic scripted responses rather than a replay cache of original provider
calls.

## Where the seams are

| Seam | Contract | Why it is a seam |
|---|---|---|
| `Chunker.chunk` | `Document -> list[Chunk]` with offsets | swapping chunking is intervention 1 |
| `Embedder.encode` | texts -> L2-normalised rows; `fingerprint()` into cache keys | a backend swap must not reuse another model's vectors |
| `Retriever.retrieve` | `(query, k) -> list[ScoredChunk]` | dense / bm25 / fusion are interchangeable |
| `Generator.generate` | `prompt -> Completion` | the only network call; `ScriptedGenerator` substitutes it in tests |
| `TraceRecord` | one JSONL line per case | the data contract every metric and report reads |

`ScoredChunk` keeps every constituent score (`dense_score`, `lexical_score`,
`rrf_score`) rather than collapsing to one number, because diagnosing a retrieval
failure requires knowing which member surfaced a chunk and which buried it.

## What is not here

- **No semantic model-assisted grading.** Every current result is deterministic.
- **No demo UI.**
- **No reranker, no query rewriting, no decomposition.** Deliberately: the
  measured baseline failure profile did not demand them, and adding them would
  have made the architecture look sophisticated while confounding the measurement.

See [`deferred-work.md`](deferred-work.md).
