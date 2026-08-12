# Results

Current conclusions use the trace-derived [corrected-v2 held-out report](../reports/corrected-v2/held-out/comparison.md).
The original held-out report remains frozen historical evidence.

## Configured-system outcomes (22 held-out cases)

The complete configured systems used different retrieval budgets: baseline k=4
and improved k=8. Under those configurations, span recall was 0.692 → 0.883,
MRR 0.667 → 0.835, precision 0.287 → 0.150, and document recall 0.921 → 0.947.
These outcomes include the different retrieval/context budgets.

## Common-budget sensitivity (post-hoc)

Both traces were capped at k=4.

| Metric | Baseline | Improved | Delta | 95% CI |
|---|---:|---:|---:|:---:|
| span recall | 0.692 | 0.750 | +0.058 | [-0.067, +0.200] |
| MRR | 0.667 | 0.817 | +0.150 | [-0.017, +0.321] |
| precision | 0.287 | 0.263 | -0.025 | [-0.113, +0.050] |
| document recall | 0.921 | 0.947 | +0.026 | [+0.000, +0.079] |

The common-budget intervals do not establish a held-out ranking advantage. This
is a post-hoc sensitivity analysis, not a preregistered endpoint.

## Withdrawn measurements

nDCG is deprecated from corrected-v2 conclusions. The original definition could
double-count one evidence span across overlapping chunks; the bounded replacement
made an unsuitable one-chunk/one-evidence-unit assumption. The historical
document-level citation-authority flag is likewise retained only as trace metadata
and is not a citation-quality conclusion.

The withdrawn measurements do not change the main interpretation: the improved
configuration retrieved more evidence at its larger configured budget, while
common-budget held-out ranking superiority was not established.
