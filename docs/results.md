# Results

Everything here carries three things: **the split it was measured on, the number
of cases behind it, and whether the metric is deterministic or model-assisted.**
All metrics below are **deterministic**. No model-assisted grading has been
implemented, so no result on this page depends on an LLM judge.

The held-out result is frozen. See
[`frozen-held-out-result.md`](frozen-held-out-result.md) for checksums and
[`statistical-audit.md`](statistical-audit.md) for the audit these readings come
from.

---

## The one-paragraph version

On a held-out split of 22 cases, the improved retrieval configuration raised MRR
from 0.667 to 0.835 and recall@10 from 0.692 to 0.883, both with a
paired-bootstrap 95% CI excluding zero. Ten of the twelve measured metrics showed
no measurable difference. **Both surviving results depend on the improved
configuration retrieving twice as many chunks as the baseline**: at a matched
retrieval budget neither interval excludes zero. The correct summary is that the
improved *configuration* retrieves the required evidence more often, not that its
*ranking* is better.

---

## Held-out split, n = 22

Baseline `baseline-test-20260806T182019Z-66ee099b` vs improved
`improved-test-20260806T182251Z-1e6a1bf8`. Generator `gemini-3.1-flash-lite`,
held constant across arms. 10,000 paired resamples, seed 20260806.

### Confirmed under the predeclared CI criterion

Both intervals exclude zero. Neither is a significance test — see
[Multiplicity](#multiplicity) and [the budget caveat](#the-budget-caveat).

| Metric | n | Baseline | Improved | Delta | 95% CI |
|---|---:|---:|---:|---:|:---:|
| MRR | 20 | 0.667 | 0.835 | +0.168 | [+0.008, +0.339] |
| recall@10 | 20 | 0.692 | 0.883 | +0.192 | [+0.025, +0.375] |

### No measurable difference

The interval contains zero. These are reported as no measurable difference, not
as improvements with a caveat.

| Metric | n | Baseline | Improved | Delta | 95% CI |
|---|---:|---:|---:|---:|:---:|
| recall@1 | 20 | 0.408 | 0.525 | +0.117 | [−0.058, +0.292] |
| recall@3 | 20 | 0.592 | 0.750 | +0.158 | [−0.008, +0.350] |
| recall@5 | 20 | 0.692 | 0.800 | +0.108 | [−0.042, +0.275] |
| precision@5 | 20 | 0.287 | 0.220 | −0.068 | [−0.163, +0.013] |
| nDCG@5 | 20 | 0.630 | 0.694 | +0.064 | [−0.088, +0.209] |
| document recall | 19 | 0.921 | 0.947 | +0.026 | [+0.000, +0.079] |
| required-fact coverage | 19 | 0.789 | 0.895 | +0.105 | [−0.079, +0.289] |
| citation precision (doc) | 16 | 0.875 | 0.838 | −0.037 | [−0.146, +0.067] |
| claim-citation coverage | 22 | 0.701 | 0.754 | +0.054 | [−0.104, +0.223] |

Document recall's interval has a lower bound of exactly +0.000, which contains
zero and is therefore no measurable difference. It is the closest call on the
page and is not treated as a near-miss.

### Unchanged

| Metric | n | Baseline | Improved | Note |
|---|---:|---:|---:|---|
| citation validity | 16 | 1.000 | 1.000 | CI exactly [0.000, 0.000] |
| fabricated citations | 22 | 0 | 0 | count, summed over cases |

Citation validity being 1.000 in both arms is a real property: citations are bound
to the context map the model was actually shown, so a label can only resolve or be
recorded as fabricated. It is also a metric with **no headroom**, which means it
cannot distinguish the two arms and should not be cited as evidence that one is
better. Neither pipeline has ever emitted an unresolvable citation, on either
split.

### Observed counts and trade-offs

Counts are summed over cases, not averaged, and carry no interval.

| Counter | Baseline | Improved | Change |
|---|---:|---:|---|
| non-authoritative citations | 4 | 7 | **+3, worse** |
| forbidden claims | 6 | 6 | no change |
| fabricated citations | 0 | 0 | no change |

**Non-authoritative citations rose.** More retrieved context means more chances to
cite a document that restates a fact rather than the one that owns it. This was
written into `configs/improved.yaml` as an expected cost before the run.

**Forbidden claims did not decrease.** Six in both arms. The improved
configuration did not reduce the rate at which designed-wrong answers appear.

That count is also a **lower bound**, not a measurement. `forbidden_claim_count`
matches on an extracted numeric or code-shaped token, so a forbidden claim
containing neither is never counted — 20 of the 67 declared across the dataset
(30%) are structurally undetectable, including `"any named bank"` and
`"presenting a response time as a resolution time"`. The direction of the bias is
unknown. This is audit finding A-3.

### Abstention

| | n | Baseline | Improved | Delta | 95% CI | |
|---|---:|---:|---:|---:|:---:|---|
| abstention accuracy | 22 | 0.818 | 0.909 | +0.091 | [−0.091, +0.273] | contains zero |

**Abstention accuracy is not a measurable difference on held-out data.** The point
estimates differ by 9 points, which sounds substantial and is not distinguishable
from noise at this sample size: with 22 cases, **one case is worth 4.5 points**, so
the entire apparent improvement is two cases changing behaviour.

On the dev split the same comparison gives +0.143 [+0.036, +0.286], which does
exclude zero. A result that holds on dev and not on held-out is the ordinary case,
not an anomaly.

| expected → observed | Baseline | Improved |
|---|---:|---:|
| `abstain→abstain` | 3 | 3 |
| `answer→abstain` | 3 | 1 |
| `answer→answer` | 14 | 16 |
| `clarify→answer` | 1 | 1 |
| `clarify→clarify` | 1 | 1 |

---

## The budget caveat

**This section governs how the two confirmed results may be described.**

The baseline retrieves `top_k = 4` chunks; the improved arm retrieves 8.
`recall_at_k` filters the stored retrieval list by `rank <= k`, so any cutoff
above an arm's `top_k` silently becomes "everything that arm retrieved". The
baseline's recall@5 and recall@10 are therefore both recall@4, and **recall@10
compares four chunks against eight.**

MRR is cleaner — it is the reciprocal rank of the first relevant chunk, which is a
ranking quantity — but it is not budget-free either: the improved arm has four
extra ranks in which to earn a non-zero score.

Recomputing both with the cutoff matched to the baseline's budget, using the
production metric functions:

| Held-out (n=20) | Delta | 95% CI | |
|---|---:|:---:|---|
| MRR, as reported (≤10) | +0.168 | [+0.008, +0.339] | excludes zero |
| **MRR, budget-matched (≤4)** | +0.150 | **[−0.017, +0.321]** | **contains zero** |
| recall@10, as reported | +0.192 | [+0.025, +0.375] | excludes zero |
| **recall@4, budget-matched** | +0.058 | **[−0.067, +0.200]** | **contains zero** |

Two cases carry it — F-04 and F-12, whose first relevant chunk sits at rank 5–8,
where the baseline structurally cannot look.

The dev-only ablation measures the same thing directly. Isolating the budget
change at both places it can be isolated, raising `top_k` from 4 to 8 changes
recall@1 and recall@3 by **exactly zero**, while moving recall@10 and document
recall and costing precision.

### Required phrasing

**Say:**

- "recall@10 is a system/context-budget result: the improved configuration
  retrieves the required evidence more often, partly because it retrieves more."
- "MRR is the cleaner retrieval-ranking result, and at a matched budget its
  interval includes zero."
- "the improved retrieval configuration" — the intervention is a bundle.
- "the paired-bootstrap 95% CI excluded zero", or "a measurable difference under
  the prespecified paired-bootstrap criterion".

**Do not say:**

- "the improved pipeline ranks better" — not established on held-out data.
- "BM25 caused…", "structure-aware chunking caused…", "hybrid retrieval caused…"
  — except when explicitly discussing the dev-only ablation below.
- "statistically significant" — no null model, no p-value, no multiplicity control.
- any improvement for a metric whose interval includes zero.

---

## Multiplicity

Twelve metrics were compared at 95% with no correction. Under a global null of no
difference, roughly **0.6 of 12 intervals would exclude zero by chance**. Two did.

That is not evidence against the findings — the two that moved are the two the
intervention most directly acts on, which is coherent — but the per-metric 95%
figure is not a family-wide error rate. No correction is applied because the
metrics are strongly dependent (all computed from the same retrieval list, and
they share bootstrap resample draws), so Bonferroni would be badly conservative
and a proper joint procedure is not justified at n=22. The multiplicity is
disclosed instead of adjusted, and the vocabulary of significance is avoided.

---

## Dev split, n = 28

The dev split is where the interventions were designed. Its numbers are reported
for completeness and are **not** evidence of generalisation.

| Metric | n | Baseline | Improved | Delta | 95% CI | |
|---|---:|---:|---:|---:|:---:|---|
| recall@1 | 28 | 0.226 | 0.333 | +0.107 | [−0.036, +0.250] | |
| recall@3 | 28 | 0.530 | 0.637 | +0.107 | [−0.042, +0.262] | |
| recall@5 | 28 | 0.530 | 0.649 | +0.119 | [−0.036, +0.280] | |
| recall@10 | 28 | 0.530 | 0.738 | +0.208 | [+0.048, +0.375] | excludes zero |
| precision@5 | 28 | 0.188 | 0.171 | −0.016 | [−0.071, +0.041] | |
| nDCG@5 | 28 | 0.437 | 0.531 | +0.093 | [−0.029, +0.221] | |
| MRR | 28 | 0.434 | 0.581 | +0.146 | [+0.027, +0.273] | excludes zero |
| document recall | 25 | 0.840 | 0.933 | +0.093 | [−0.007, +0.207] | |
| required-fact coverage | 25 | 0.720 | 0.853 | +0.133 | [+0.033, +0.260] | excludes zero |
| citation validity | 21 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] | |
| citation precision (doc) | 21 | 0.889 | 0.895 | +0.006 | [−0.075, +0.095] | |
| claim-citation coverage | 28 | 0.712 | 0.811 | +0.099 | [−0.023, +0.241] | |
| abstention accuracy | 28 | 0.750 | 0.893 | +0.143 | [+0.036, +0.286] | excludes zero |

Required-fact coverage and abstention accuracy exclude zero on dev and **not** on
held-out. That is the single most useful comparison on this page: two of the four
dev findings did not survive a split the interventions were not designed against.

Budget-matched MRR on dev is +0.131 [+0.006, +0.262] — still excluding zero. So a
ranking effect is visible on dev and is not established on held-out once the
budget is held constant.

---

## Failure classification

Automatic, from trace signals, using the ordered rules in
[`failure-taxonomy.md`](failure-taxonomy.md).

| | dev (n=28) | held-out (n=22) |
|---|---|---|
| cases failing, baseline → improved | 18 → 14 | 11 → 10 |

Held-out class movement:

| Class | Baseline | Improved | Change |
|---|---:|---:|---:|
| retrieval_miss | 4 | 1 | −3 |
| retrieval_partial_multihop | 3 | 4 | +1 |
| evidence_ranked_low | 2 | 2 | 0 |
| unsupported_claim | 1 | 2 | +1 |
| ambiguity_collapse | 1 | 1 | 0 |

**The improved configuration converts total misses into partial misses.** That is
mechanically why rank-sensitive metrics over a wide window moved while
common-cutoff recall did not: evidence now enters the candidate window without
reliably reaching the top of it.

One case, **F-14**, regressed on held-out (`ok` → `unsupported_claim`, gaining a
forbidden claim and a non-authoritative citation). Nine cases fail in both arms:
A-05, A-07, B-02, B-05, F-04, M-04, M-08, T-02, T-03 — clustered in ambiguity
handling, superseded-policy questions, and multi-hop aggregation. None of those
was targeted by the interventions.

---

## Dev-only retrieval ablation

**Explanatory only, dev split only, and it selects nothing.** The improved arm
stays frozen regardless of what this table shows. Component interactions mean
these are descriptive comparisons, not a factorial causal study — six of sixteen
cells, with components that are not independent.

Variant A reproduces the frozen baseline arm and F the frozen improved arm
exactly, so the harness measures what the frozen runs measured.

| | Variant | r@1 | r@3 | MRR | nDCG@5 | P@5 | doc recall |
|---|---|---:|---:|---:|---:|---:|---:|
| A | baseline (fixed, dense, k=4) | 0.226 | 0.530 | 0.435 | 0.437 | 0.188 | 0.840 |
| B | structure-only (k=4) | 0.387 | 0.554 | 0.574 | 0.538 | 0.223 | 0.913 |
| C | hybrid-only (k=4) | 0.214 | 0.470 | 0.399 | 0.433 | 0.196 | 0.860 |
| D | budget-only (k=8) | 0.226 | 0.530 | 0.440 | 0.450 | 0.164 | 0.927 |
| E | structure+hybrid (k=4) | 0.333 | 0.637 | 0.565 | 0.531 | 0.214 | 0.893 |
| F | full improved (k=8, dedupe) | 0.333 | 0.637 | 0.581 | 0.531 | 0.171 | 0.933 |

Only recall@1 and recall@3 are comparable across every row; for the k=4 variants,
recall@5 and recall@10 are both recall@4.

Three descriptive findings, on **dev only**:

1. **Structure-aware chunking accounts for most of the ranking gain.** Alone it
   moves recall@1 by +0.161 and MRR by +0.140, and it beats the full bundle on
   recall@1 (0.387 vs 0.333) and precision@5 (0.223 vs 0.171).
2. **Hybrid fusion alone is negative** on recall@1, recall@3, MRR and nDCG@5. It
   pays off only in combination with structure-aware chunking, and even then it
   raises recall@3 while lowering recall@1 relative to structure alone.
3. **Raising `top_k` buys coverage and nothing else**: +0.000 on both recall@1 and
   recall@3 in both isolations, while moving recall@10 and document recall and
   costing precision.

None of this licenses reconfiguring the pipeline. Acting on "B beats F on
recall@1" would mean selecting a configuration using dev data and then having no
untouched split on which to test it.

---

## What these results are not

- Not evidence about production RAG systems. One synthetic corpus, one embedding
  model, one generator, 50 cases.
- Not evidence that the improved pipeline ranks better. See the budget caveat.
- Not evidence about grounding quality beyond citation *resolution*. Citation
  validity checks that a label points at a chunk the model was shown; it does not
  check that the chunk **entails** the claim. That would need the judge, which is
  not implemented.
- Not a statement about any component in isolation, except within the dev-only
  ablation, and there only descriptively.

Full boundary conditions: [`limitations.md`](limitations.md).
