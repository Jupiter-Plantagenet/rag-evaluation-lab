# Corrected derived metrics v2 — held-out

This is a trace-only re-score. The original traces and frozen reports remain unchanged.

- source runs: `baseline-test-20260806T182019Z-66ee099b` / `improved-test-20260806T182251Z-1e6a1bf8`
- source trace SHA-256: `f7c2df4ceb322c817e5cc7a6bbf083f9dd471f70172f20a3f01f199e74164352` / `1f13b109a811d43d45650850d063c68716dd7741a1150f8eb03fbeff1b2299f8`
- corrected metric version: `2.1.0`
- metric change: nDCG is deprecated from v2 conclusions: the original definition double-counted overlapping chunks, while the bounded replacement incorrectly limited one retrieved chunk to one evidence unit.
- current retrieval metrics: evidence-span recall, MRR, precision, and document recall.
- citation authority: the historical document-level flag is deprecated trace metadata and is not a citation-quality conclusion.

## Configured-system outcomes

Outcomes of the complete configured pipelines at their actual retrieval budgets.

Baseline: k=4; improved: k=8.

| Metric | n | Baseline | Improved | Delta | 95% CI |
|---|---:|---:|---:|---:|:---:|
| span recall | 20 | 0.692 | 0.883 | +0.192 | [+0.025, +0.375] |
| MRR | 20 | 0.667 | 0.835 | +0.168 | [+0.007, +0.339] |
| precision | 20 | 0.287 | 0.150 | -0.138 | [-0.225, -0.056] |
| document recall | 19 | 0.921 | 0.947 | +0.026 | [+0.000, +0.079] |

## Common-budget ranking sensitivity (post-hoc)

Post-hoc sensitivity analysis with both arms capped at the same candidate budget.

Both arms capped at k=4.

| Metric | n | Baseline | Improved | Delta | 95% CI |
|---|---:|---:|---:|---:|:---:|
| span recall | 20 | 0.692 | 0.750 | +0.058 | [-0.067, +0.200] |
| MRR | 20 | 0.667 | 0.817 | +0.150 | [-0.017, +0.321] |
| precision | 20 | 0.287 | 0.263 | -0.025 | [-0.113, +0.050] |
| document recall | 19 | 0.921 | 0.947 | +0.026 | [+0.000, +0.079] |
