# Corrected release v2

An independent review found metric-definition defects and stale public evidence
claims. This release corrects reporting from stored traces; it does not rerun
models or alter frozen experimental artefacts.

## Original issues found

- The original nDCG definition could double-count one evidence span across
  overlapping retrieved chunks and exceed 1.
- The document-level citation `authoritative` flag could not establish source
  authority for a specific claim, fact, or effective date.
- Dataset, trace, response-cache, CI-status, and held-out-access wording had
  drifted from the repository evidence.

## Final treatment

- **nDCG is deprecated from corrected-v2 conclusions rather than replaced.** The
  bounded replacement was explored, but imposed a one-chunk/one-evidence-unit
  assumption inappropriate when a single chunk contains multiple required spans.
- Citation authority is removed from current reporting and retained only as
  historical trace metadata.
- Current recall, MRR, precision, and document-recall results are re-derived from
  frozen traces in `reports/corrected-v2/`.
- New runs, comparison reports, and the current development ablation do not
  compute or present nDCG.
- Original traces, historical held-out report, configurations, and access ledger
  remain unchanged and checksum-verified.

## Impact

The formerly displayed held-out nDCG@5 values (baseline 0.630, improved 0.694)
are historical measurements affected by the definition defect. They are
withdrawn, not replaced: no corrected-v2 nDCG result is reported. The historical
citation-authority count (4 → 7) is likewise withdrawn. The current
configured-system results remain span recall 0.692 → 0.883 and MRR 0.667 →
0.835; at common k=4, MRR is +0.150 with CI [-0.017, +0.321] and span recall
+0.058 with CI [-0.067, +0.200].

The main held-out interpretation is unchanged: the complete improved
configuration retrieved more evidence over its larger retrieval/context budget,
but the common-budget sensitivity did not establish superior ranking.
