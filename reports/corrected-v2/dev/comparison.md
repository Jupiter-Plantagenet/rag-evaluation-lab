# Corrected derived metrics v2 — dev

This is a trace-only re-score. The original traces and frozen reports remain unchanged.

- source runs: `baseline-dev-20260806T180859Z-66ee099b` / `improved-dev-20260806T181347Z-1e6a1bf8`
- source trace SHA-256: `5c1bbe578f757c35a51151f1e177477b4e35b734237d5cbbe3381b396a4b3506` / `b4c06f6df024ca039b369f85e879544dc52db1ea6449d4cb412dcdffbef5a224`
- corrected metric version: `2.1.0`
- metric change: nDCG is deprecated from v2 conclusions: the original definition double-counted overlapping chunks, while the bounded replacement incorrectly limited one retrieved chunk to one evidence unit.
- current retrieval metrics: evidence-span recall, MRR, precision, and document recall.
- citation authority: the historical document-level flag is deprecated trace metadata and is not a citation-quality conclusion.

## Configured-system outcomes

Outcomes of the complete configured pipelines at their actual retrieval budgets.

Baseline: k=4; improved: k=8.

| Metric | n | Baseline | Improved | Delta | 95% CI |
|---|---:|---:|---:|---:|:---:|
| span recall | 28 | 0.530 | 0.738 | +0.208 | [+0.048, +0.375] |
| MRR | 28 | 0.434 | 0.581 | +0.146 | [+0.027, +0.273] |
| precision | 28 | 0.188 | 0.130 | -0.058 | [-0.112, -0.004] |
| document recall | 25 | 0.840 | 0.933 | +0.093 | [-0.007, +0.207] |

## Common-budget ranking sensitivity (post-hoc)

Post-hoc sensitivity analysis with both arms capped at the same candidate budget.

Both arms capped at k=4.

| Metric | n | Baseline | Improved | Delta | 95% CI |
|---|---:|---:|---:|---:|:---:|
| span recall | 28 | 0.530 | 0.649 | +0.119 | [-0.036, +0.280] |
| MRR | 28 | 0.434 | 0.566 | +0.131 | [+0.006, +0.262] |
| precision | 28 | 0.188 | 0.214 | +0.027 | [-0.036, +0.089] |
| document recall | 25 | 0.840 | 0.893 | +0.053 | [-0.080, +0.187] |
