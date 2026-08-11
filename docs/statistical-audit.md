# Statistical audit of the comparison reporting

Scope: `src/rag_eval/reporting/compare.py` and the parts of
`src/rag_eval/evaluation/metrics.py` it consumes, audited against the stored
per-case values in the four committed run traces.

Method: every number in the frozen held-out report was recomputed independently
from `trace.jsonl` — a second implementation of the paired bootstrap written
against the stored per-case metrics, not a re-run of `build_comparison`. Nothing
was regenerated. The frozen artefacts are byte-identical to their recorded
checksums (`scripts/verify_frozen.py`).

---

## Verdict

**The frozen held-out report is arithmetically correct.** All 12 metrics
reproduce exactly — identical `n_paired`, `delta`, `ci_low`, `ci_high`. The
pairing is genuinely paired, cases undefined in either arm are correctly
excluded, the seed makes the intervals reproducible, and the mean of per-case
differences equals the difference of means to 1.5 × 10⁻¹⁶.

**But the two "improved" verdicts do not mean what a reader will assume they
mean.** Both depend on the improved arm being allowed to retrieve twice as many
chunks. That is finding **A-13**, it is the most important result of this audit,
and it is an interpretation defect rather than a computation defect. The numbers
are right; the sentence a reader forms from them is wrong.

No finding requires the frozen report to be withdrawn or re-issued. Two findings
(A-2, A-3) are definitional and should be fixed *before the next measurement*,
not retrospectively.

---

## A-13 — the confirmed results are context-budget results, not ranking results

**Severity: high (interpretive). Affects both headline claims.**

The baseline retrieves `top_k = 4` chunks. The improved arm retrieves `top_k = 8`.
`recall_at_k` filters the stored retrieval list by `rank <= k`, so a cutoff larger
than an arm's `top_k` silently degrades to "everything that arm retrieved":

| | chunks retrieved | recall@3 | recall@5 | recall@10 |
|---|---|---|---|---|
| baseline | always 4 | true cutoff | = recall@4 | = recall@4 |
| improved | 7–8 | true cutoff | true cutoff | = recall@8 |

So **`recall_at_10` compares 4 chunks against 8 chunks.** It is a measure of the
system including its context budget, not of ranking quality at a common cutoff.
Only `recall@1` and `recall@3` are true common-cutoff comparisons, and both of
those are reported as no measurable difference.

MRR is cleaner but **not budget-free**: the improved arm has four extra ranks in
which to earn a non-zero reciprocal rank. Recomputing both headline metrics with
the cutoff matched to the baseline's budget (ranks 1–4 for both arms), using the
production metric functions:

| Held-out (n=20) | Baseline | Improved | Delta | 95% CI | Verdict |
|---|---:|---:|---:|:---:|---|
| MRR, as reported (≤10) | 0.667 | 0.835 | +0.168 | [+0.008, +0.339] | CI excludes zero |
| **MRR, budget-matched (≤4)** | 0.667 | 0.817 | +0.150 | **[−0.017, +0.321]** | **contains zero** |
| recall@10, as reported | 0.692 | 0.883 | +0.192 | [+0.025, +0.375] | CI excludes zero |
| **recall@4, budget-matched** | 0.692 | 0.750 | +0.058 | **[−0.067, +0.200]** | **contains zero** |

**At a matched retrieval budget, neither held-out result excludes zero.** Two
cases carry it — F-04 and F-12, whose first relevant chunk sits at rank 5–8 where
the baseline structurally cannot look.

On the dev split the picture differs: budget-matched MRR is +0.131
[+0.006, +0.262], still excluding zero. So a ranking effect is visible on dev and
is *not* established on held-out once the budget is held constant.

This does not invalidate the frozen result. Doubling `top_k` is a real,
deliberate, pre-registered intervention, and "the improved configuration
retrieves the evidence more often" is a true and useful claim. What cannot be
claimed is that the *ranking* improved on held-out data. Required phrasing is set
out in [`results.md`](results.md).

**Recommended for the next measurement, not retrospectively:** report every
rank-sensitive metric at a cutoff no larger than the smallest arm's `top_k`, and
report the budget-varying comparison separately and by that name.

---

## Findings

Severity is about the risk of a reader forming a false belief, not about how
wrong the arithmetic is.

| ID | Finding | Severity | Status |
|---|---|---|---|
| A-13 | Confirmed results are context-budget results (above) | high | documented; phrasing constrained in `results.md` |
| A-3 | 30% of forbidden claims are structurally undetectable | medium | documented; deferred fix |
| A-8 | No multiple-comparison control across 12 metrics | medium | disclosed in the report itself |
| A-2 | `expected_document_ids` omits documents holding expected spans | medium | documented; deferred fix |
| A-7 | `significant` claimed a test that never ran | medium | **fixed** (renamed) |
| A-4 | Per-category means were per-arm, not paired | low | **fixed** (no number changed) |
| A-1 | An unanswerable case enters retrieval-metric denominators | low | documented; verdicts unaffected |
| A-12 | Error-cases dropped per arm without disclosure | low | documented; no impact (0 errors) |
| A-5 | `p50`/`p95` are order statistics, not percentile estimates | low | already disclosed in the report |
| A-6 | `direction` assumes higher-is-better | latent | **pinned by test** |
| A-11 | One seed shared across metrics correlates the intervals | informational | documented |
| A-9 | `metrics.bootstrap_ci` is unused by production code | trivial | documented |
| A-10 | Bootstrap resamples values, not indices | none | verified equivalent |

### A-3 — 30% of forbidden claims cannot be detected

`forbidden_claim_count` extracts a numeric or code-shaped token from each declared
forbidden claim and tests whether it appears in the answer. Claims containing no
such token match nothing and are **never counted**.

Of 67 forbidden claims declared across the dataset, **20 (30%) have no extractable
token**, including:

- `"any named bank"` (U-04)
- `"Yes, there is an iOS SDK"`, `"Swift"`, `"Kotlin"` (U-02)
- `"presenting a response time as a resolution time"` (B-03)
- `"citing product-overview or subscription-plans as the authoritative source"` (C-02)
- `"a fraud block (the evidence points to a volume limit, not risk)"` (M-06)

The reported counter `forbidden_claims: 6 → 6` on held-out is therefore a count
over the detectable subset only. It is a lower bound, and the *direction* of the
bias is unknown: an arm could be emitting undetectable forbidden claims freely.

The metric's docstring already says matching is loose; what it does not say is
that a declared claim can be silently outside the instrument's reach. **The count
must be reported as a lower bound over a detectable subset, with the subset size
stated.** Fixing this properly means giving each forbidden claim an explicit
matcher — a dataset change, deferred.

### A-8 — twelve metrics, one confidence level, no correction

The report compares 12 metrics at 95%. Under a global null of no difference one
would expect ≈ 0.6 intervals to exclude zero by chance. Two did.

That is not evidence *against* the findings — the two that moved are the two the
intervention most directly acts on, which is coherent — but it does mean the
per-metric 95% figure is not a family-wide error rate. The word "significant" has
been removed from the code, the schema, and the prose for this reason, and the
generated report now states the expected false-exclusion count inline.

No correction is applied because the metrics are strongly dependent (they are
computed from the same retrieval list, and A-11 means they share resample draws),
so Bonferroni would be badly conservative and a proper joint procedure is not
justified at n=22. **The honest position is to disclose the multiplicity and
avoid the vocabulary of significance**, which is what is now done.

### A-2 — evidence spans in documents the ground truth does not list

Two held-out cases declare `expected_evidence_spans` in a document absent from
their `expected_document_ids`:

| Case | Spans in | `expected_document_ids` |
|---|---|---|
| F-08 | `product-overview` | `regional-restrictions` |
| C-02 | `product-overview` | `pricing-and-fees` |

Two consequences:

1. `document_recall` scores 1.000 for both cases in both arms while a document
   holding expected evidence was never required — the metric is easier than
   intended.
2. `citation_precision_doc` treats a citation to `product-overview` as off-target
   even though it holds an expected span, so citation precision is **understated
   in both arms**.

Sensitivity, taking expected documents as `expected_document_ids ∪ span doc_ids`:

| Held-out citation precision | Baseline | Improved | Delta | 95% CI |
|---|---:|---:|---:|:---:|
| as shipped | 0.875 | 0.838 | −0.037 | [−0.146, +0.067] |
| widened definition | 0.938 | 0.890 | −0.048 | [−0.158, +0.067] |

Both arms rise ≈ 6 points; the verdict (no measurable difference) is unchanged.
The dataset validator does not currently check this invariant — it should, and
that is a deferred item.

### A-1 — an unanswerable case scored for retrieval

Four unanswerable cases (U-01, U-02, U-05 on dev; **U-06** on held-out) declare no
`expected_document_ids` but do carry one non-authoritative `expected_evidence_span`.
Retrieval recall is therefore *defined* for them while document recall is not,
which is why `recall@k` has n=20 and `document_recall` n=19 on a 22-case split.

U-06 scores 1.000 in both arms, so it contributes a tied pair. The effect is
conservative — a tied pair pulls the paired mean toward zero and narrows the
interval. Removing it changes no verdict (full table in
[`frozen-held-out-result.md`](frozen-held-out-result.md)).

### A-12 — cases with errors are dropped without disclosure

`build_comparison` filters `if not r["errors"]` per arm before intersecting. A run
with errors would silently shrink `n_cases`, and the report would state the
reduced number with no indication that anything was dropped or which arm dropped
it. Both frozen runs have zero errors, so the frozen result is unaffected. The
report should name dropped cases; deferred.

### A-5 — `p50` and `p95` are order statistics

`p50_ms` is `values[n // 2]`, the upper-middle observation, not the average of the
two central values for even n. `p95_ms` is `values[min(int(n * 0.95), n - 1)]` —
at n=22 that is index 20, the second-worst observation. The report already
discloses the p95 behaviour in a footnote. Neither is used for any claim.

### A-6 — `direction` assumes every metric is higher-is-better

`direction = "improved" if delta > 0 else "regressed"` is unconditional. True for
all 12 current metrics; wrong the moment an error rate or a latency is added to
`METRICS`, and wrong *silently*, reporting a regression as an improvement.
`test_direction_assumes_higher_is_better_for_every_declared_metric` now fails if
such a metric is added.

### A-11 — one seed across all metrics

`compare_metric` constructs `default_rng(seed)` fresh per metric with the same
seed, so metrics with equal n draw identical resample indices. This is good for
reproducibility and means the 12 intervals are not independent draws — relevant
to A-8, and a reason a naive multiplicity correction would be wrong.

### A-10 — resampling values rather than indices (verified correct)

`rng.choice(diffs, size=(resamples, n))` resamples the per-case *difference
values*. For a statistic that is the mean of those differences this is exactly
equivalent to resampling case indices, and the pairing is preserved because the
difference is formed per case *before* resampling. Verified by
`test_paired_bootstrap_is_paired_not_independent`: perfectly correlated arms
return a zero-width interval, which an unpaired procedure could not produce.

---

## Changes made

1. **`significant` → `ci_excludes_zero`** in `MetricComparison`, `to_dict()`, and
   the CSV header. The name now states the fact rather than implying a test.
2. **Per-category means are paired** (A-4). Previously each arm averaged over its
   own defined cases, so a row's two numbers could describe different case sets.
   Verified a no-op on both splits — every per-category value is unchanged — and
   the paired denominators are now printed beside the means.
3. **Abstention accuracy gets a paired bootstrap interval.** Two bare proportions
   invite subtraction; at n=22 one case moves accuracy by 4.5 points.
4. **The generated report states its own multiplicity** (A-8) and no longer uses
   the word "significant" anywhere.
5. **17 unit tests** in `tests/unit/test_compare_statistics.py`, covering pairing,
   case-ID alignment, None-exclusion, one-armed exclusion, seed determinism,
   two-sided percentiles, the zero-boundary condition, insufficient-data handling,
   regression detection, direction polarity, and both serialisation names.

`reports/dev/*` was regenerated with the audited code. Every metric value,
counter, abstention accuracy, confusion cell, latency figure, provenance field and
per-category value is identical to the previously committed version; the only
differences are the renamed field and the added columns.

`reports/held-out/*` was **not** regenerated and its checksums are unchanged. It
retains the old `significant` field name, as recorded in
[`frozen-held-out-result.md`](frozen-held-out-result.md).

## New abstention interval

Computed during the audit; not previously reported.

| Split | n | Baseline | Improved | Delta | 95% CI | |
|---|---:|---:|---:|---:|:---:|---|
| dev | 28 | 0.750 | 0.893 | +0.143 | [+0.036, +0.286] | excludes zero |
| **held-out** | 22 | 0.818 | 0.909 | +0.091 | **[−0.091, +0.273]** | **contains zero** |

The abstention-accuracy improvement is a measurable difference on dev and **not**
on held-out. Any prose describing it must say so.
