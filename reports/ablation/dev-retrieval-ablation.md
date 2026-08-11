# Dev-only retrieval ablation

- split: **dev** (n=28). The held-out split is not read by this analysis.
- embedder: `minilm` (as used by both frozen arms)
- hit coverage threshold: 0.5
- no generation calls; retrieval metrics are a pure function of the retrieved list

> **Explanatory only.** These numbers exist to attribute the package-level
> difference to components. They do **not** select a new configuration: the
> improved arm is frozen, and no variant below may be promoted on the strength
> of this table.

> **Descriptive, not a factorial causal study.** Six of the sixteen cells of a
> 2x2x2x2 design are run, and the components interact -- near-duplicate removal
> does nothing at a k too small to admit duplicates, and hybrid fusion changes
> which chunks exist to be deduplicated. Differences between rows are therefore
> not clean main effects, and no confidence intervals are given: these are
> single deterministic runs over one 28-case split, not repeated measurements.

## Configurations

| | Variant | Chunker | Retrieval | top_k | Dedupe | Chunks | Note |
|---|---|---|---|---:|---|---:|---|
| A | baseline | fixed_size | dense | 4 | no | 164 | the frozen baseline arm's retrieval |
| B | structure-only | markdown_structure | dense | 4 | no | 136 | intervention 1 alone |
| C | hybrid-only | fixed_size | hybrid_rrf | 4 | no | 164 | intervention 2 alone |
| D | budget-only | fixed_size | dense | 8 | no | 164 | intervention 3 alone |
| E | structure+hybrid | markdown_structure | hybrid_rrf | 4 | no | 136 | interventions 1+2 |
| F | full improved | markdown_structure | hybrid_rrf | 8 | yes | 136 | the frozen improved arm |

## Retrieval metrics

| | Variant | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | precision_at_5 | ndcg_at_5 | document_recall | mean ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | baseline | 0.226 | 0.530 | 0.530 | 0.530 | 0.435 | 0.188 | 0.437 | 0.840 | 24.75 |
| B | structure-only | 0.387 | 0.554 | 0.637 | 0.637 | 0.574 | 0.223 | 0.538 | 0.913 | 24.41 |
| C | hybrid-only | 0.214 | 0.470 | 0.500 | 0.500 | 0.399 | 0.196 | 0.433 | 0.860 | 46.4 |
| D | budget-only | 0.226 | 0.530 | 0.554 | 0.583 | 0.440 | 0.164 | 0.450 | 0.927 | 48.89 |
| E | structure+hybrid | 0.333 | 0.637 | 0.649 | 0.649 | 0.565 | 0.214 | 0.531 | 0.893 | 36.73 |
| F | full improved | 0.333 | 0.637 | 0.649 | 0.738 | 0.581 | 0.171 | 0.531 | 0.933 | 88.61 |

## Change from A (baseline)

| | Variant | recall_at_1 | recall_at_3 | recall_at_5 | recall_at_10 | mrr | precision_at_5 | ndcg_at_5 | document_recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B | structure-only | +0.161 | +0.024 | +0.107 | +0.107 | +0.140 | +0.036 | +0.101 | +0.073 |
| C | hybrid-only | -0.012 | -0.060 | -0.030 | -0.030 | -0.036 | +0.009 | -0.005 | +0.020 |
| D | budget-only | +0.000 | +0.000 | +0.024 | +0.054 | +0.005 | -0.023 | +0.013 | +0.087 |
| E | structure+hybrid | +0.107 | +0.107 | +0.119 | +0.119 | +0.131 | +0.027 | +0.093 | +0.053 |
| F | full improved | +0.107 | +0.107 | +0.119 | +0.208 | +0.146 | -0.016 | +0.093 | +0.093 |

## Reading `recall_at_10`

`recall_at_k` filters the retrieved list by `rank <= k`, so a cutoff above a
variant's `top_k` degrades to 'everything this variant retrieved'. For the k=4
variants (A, B, C, E) recall@5 and recall@10 are both recall@4. Compare rows at
a cutoff no larger than the smallest `top_k` involved -- recall@1 and recall@3
are the only columns comparable across every row. This is audit finding A-13.

## Attribution at a matched budget (k=4 only)

A, B, C and E all retrieve four chunks, so every column below is a like-for-like
comparison and any difference is attributable to chunking or fusion rather than
to how much context the variant was allowed.

| | Variant | recall_at_1 | recall_at_3 | mrr | ndcg_at_5 | precision_at_5 |
|---|---|---:|---:|---:|---:|---:|
| A | baseline | 0.226 | 0.530 | 0.435 | 0.437 | 0.188 |
| B | structure-only | 0.387 | 0.554 | 0.574 | 0.538 | 0.223 |
| C | hybrid-only | 0.214 | 0.470 | 0.399 | 0.433 | 0.196 |
| E | structure+hybrid | 0.333 | 0.637 | 0.565 | 0.531 | 0.214 |

## The budget component, isolated

Two pairs differ only by `top_k` (and, for E->F, the near-duplicate removal that
only becomes active at the larger k).

| Pair | Change | recall_at_1 | recall_at_3 | recall_at_10 | mrr | precision_at_5 | document_recall |
|---|---|---:|---:|---:|---:|---:|---:|
| A -> D | k 4->8, fixed+dense | +0.000 | +0.000 | +0.054 | +0.005 | -0.023 | +0.087 |
| E -> F | k 4->8 + dedupe | +0.000 | +0.000 | +0.089 | +0.016 | -0.043 | +0.040 |
