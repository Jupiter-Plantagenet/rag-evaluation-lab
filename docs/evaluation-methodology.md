# Evaluation methodology

## Design and split protocol

The baseline and improved configurations answer the same cases with the same
generator, prompt template, and seed. They differ in retrieval configuration:
baseline uses fixed-size chunks, dense retrieval, and k=4; improved uses
structure-aware chunks, hybrid retrieval, deduplication, and k=8.

The dataset has 50 cases: 28 development and 22 held-out. The documented
experimental run path requires explicit `allow_test=True` / `--final`; accesses
through that path are logged in `runs/.test_ledger.jsonl`. The ledger records the
two declared experimental accesses, and repository history is consistent with
the intended protocol. This is procedural evidence, not physical access control.

## Current metrics

- **Evidence-span recall:** fraction of expected evidence spans covered within
  the stated candidate budget; multi-hop cases receive credit per span.
- **MRR:** reciprocal rank of the first evidence-relevant chunk.
- **Precision:** share of retrieved chunks that cover at least one expected span.
- **Document recall:** fraction of declared target documents retrieved.
- **Citation resolution:** label validity, claim-citation coverage, document
  targeting where defined, and fabricated/unresolved labels.
- **Abstention:** answer, abstain, and clarify outcomes are evaluated separately.

A chunk covers an evidence span at 50% overlap. Undefined retrieval metrics
return `None`, not zero. No metrics are blended into a single score.

nDCG is deprecated from corrected-v2 conclusions. Its original definition could
double-count overlapping chunks; a bounded replacement made an unsuitable
one-chunk/one-evidence-unit assumption. Citation authority is also deprecated:
a document-level ownership flag cannot establish source authority for a specific
claim, fact, or effective date.

Citation resolution does not establish semantic entailment. Semantic
model-assisted grading is not part of this release.

## Comparison interpretation

Configured-system outcomes use each arm's actual retrieval budget. The
common-budget analysis caps both arms at k=4 and is a post-hoc sensitivity
analysis. Paired bootstrap intervals use 10,000 seeded resamples of per-case
differences. An interval containing zero is reported as no measurable difference;
this is not a significance test.
