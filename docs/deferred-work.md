# Deferred work

Things this repository was designed for and does not do. Listed so that the gap
between the design and the build is visible rather than inferred from a missing
file.

## How to read this list

Everything below is a **research extension**, not an unfinished obligation. The
case study has an accepted scope, and it is complete within it.

**Accepted current scope.** A deterministic evaluation harness for
document-grounded RAG, measured on one synthetic corpus with a 50-case versioned
dataset and a 22-case held-out split that was read exactly twice and is now
frozen. Everything published rests on deterministic metrics. The verification pass
that audited those statistics, built the test suites and corrected the claim
boundary is finished.

**Future research extensions.** Items 1–2 and 4–10 below. Each would let the
project answer a *different* question — whether citations entail their claims,
whether the harness generalises to prose its author did not write, what the
interventions cost in money. None of them is required for the current claims to
be true, and none blocks describing this work publicly.

**Genuine blockers — to broader claims only.** Three, and each blocks a specific
sentence rather than the project:

| Blocker | What it forbids saying |
|---|---|
| No judge (item 1) | that citations are *supported*, only that they *resolve* |
| Budget confound, audit A-13 (item 5) | that the improved configuration *ranks* better on held-out data |
| n = 22, no multiplicity control (item 8) | "statistically significant"; any claim resting on ten inconclusive metrics |

All three are already stated in [`results.md`](results.md),
[`limitations.md`](limitations.md) and the README. A claim boundary that is
documented is not a blocker to publication — it is what makes publication honest.

Items are ordered by what would most change the strength of the evidence.

---

## 1. Model-assisted grading (the judge)

**Status: not implemented.** `src/rag_eval/judge/` is an empty package. `rubrics/`
is empty. `EvaluationConfig.judge_enabled` and `judge_model` exist and are inert.
`evaluator_outputs` is an empty list in all 100 committed trace records.

**Why it matters most.** The deterministic metrics have run out of resolution
exactly where the interesting question lives. Citation validity is 1.000 in both
arms with an interval of [0.000, 0.000] — it verifies that a label resolves to a
chunk the model was shown, and cannot verify that the chunk **entails** the claim.
The nine held-out cases that fail in both arms are clustered in ambiguity handling
and superseded-policy reasoning, which no deterministic matcher reaches.

**What it would need**, per the original design: versioned rubrics, recorded judge
model and parameters, structured rationales, a human-override file that re-runs
respect, and a published grader-agreement figure against human labels on a sample.
Judging with a different model family than the generator is a *partial* mitigation
of self-preference bias and must be reported as partial.

**Bar for shipping it:** an agreement figure must be published before any
judge-derived number is quoted. LLM grading is a measurement with error, not
ground truth.

---

## 2. Wire the failure taxonomy into the runner

**Status: implemented and unit-tested; not wired.** `TraceRecord.failure_classes`
is an empty list in all four committed runs. The distributions in
[`failure-taxonomy.md`](failure-taxonomy.md) were produced by running the
classifier over the committed traces out-of-band.

Classification is a pure function of a stored trace, so this is a re-scoring
change requiring no model calls. It should populate `failure_classes`, add a
taxonomy section to the comparison report, and print the reconciliation note
explaining why the taxonomy's behavioural counts are lower than the abstention
table's.

---

## 3. Fix the two dataset inconsistencies

Both were found in the Phase-4 audit and both are **deliberately unfixed**,
because fixing them would change the frozen held-out numbers.

- **A-1** — four unanswerable cases (U-01, U-02, U-05 dev; U-06 held-out) carry an
  evidence span but declare no `expected_document_ids`, so retrieval recall is
  defined for them while document recall is not.
- **A-2** — F-08 and C-02 declare spans in `product-overview`, which is absent from
  their `expected_document_ids`. Document recall is easier than intended and
  citation precision is understated in both arms by about 6 points.

`scripts/validate_dataset.py` does not currently check either invariant. It should.
Any fix must be published as a **new report version**, never as an edit to the
frozen artefacts.

---

## 4. Make forbidden claims measurable

`forbidden_claim_count` matches on an extracted numeric or code-shaped token, so
20 of 67 declared forbidden claims (30%) — `"any named bank"`, `"Swift"`,
`"presenting a response time as a resolution time"` — are never counted. The
reported counts are lower bounds over a detectable subset with an unknown bias
direction.

The fix is a dataset change: give each forbidden claim an explicit matcher, the
same way `required_facts` already does. Until then every count must be reported as
a lower bound with its subset size.

---

## 5. Report rank-sensitive metrics at a matched budget

Audit finding A-13. `recall_at_k` degrades to "everything this arm retrieved" once
`k` exceeds the arm's `top_k`, so `recall_at_10` compared 4 chunks against 8.

Future comparisons should report every rank-sensitive metric at a cutoff no larger
than the smallest arm's `top_k`, and report the budget-varying comparison
separately and under that name. The frozen result stands as published; this
changes how the next one is measured.

---

## 6. Cost accounting

`estimated_cost_usd` is 0.0000 in every record because the runs used a free tier,
while prompt tokens roughly doubled between arms. The doubled context is a real
cost currently priced at zero. Tokens should be reported as measured and cost as
an explicitly-labelled counterfactual using the pinned models' published list
prices.

---

## 7. A committed CI replay cache

`.gitignore` budgets `tests/fixtures/cache/` at under 2 MB as a curated replay
subset, and CI sets `RAG_EVAL_CACHE_DIR` to it. The directory is empty.

The integration suite works around this with a frozen in-process generator, which
tests the pipeline but not the cache-replay path itself. A recorded subset would
let CI replay real model outputs.

---

## 8. Statistical power

Ten of twelve held-out metrics returned intervals containing zero, and one case is
worth 4.5 points. The dataset was already expanded once (34 → 50 cases) in
anticipation; it was not enough.

Meaningfully improving power means substantially more cases — and, if any new
intervention is to be tested, a **fresh held-out split**, because the current one
is spent. Its per-case failure profile is now documented, so designing against it
would be tuning on the test set.

---

## 9. The second corpus

The design called for an optional public corpus (SQLite's public-domain
documentation), *fetched* and never redistributed, as a check that the harness is
not overfitted to prose its author wrote. Not implemented; `docs/corpora.md` does
not exist.

This is the cheapest available test of the largest external-validity threat in
[`limitations.md`](limitations.md).

---

## 10. Demo UI

`src/rag_eval/demo/` is an empty package. The intended demo serves stored traces —
retrieved chunks, the exact context, resolved citations with their source spans —
rather than being a chatbot. Its value is showing the evidence behind an answer,
which is the thing a chatbot demo hides.

Explicitly **not** a "demo mode": the predecessor project's demo mode bypassed
retrieval and returned hard-coded strings, so it shared no code path with the
system it demonstrated.

---

## 11. Publication

**Status: packaging complete; not published.**

The case study, portfolio copy, visuals, demo script and publication checklist are
in [`portfolio/`](../portfolio/), with generated figures in
[`assets/charts/`](../assets/charts/).

Packaging was gated on the **verification** work — the statistical audit, the
integration and regression suites, and the corrected claim boundary — because
publishing a result before its measurement gaps are *known* is how claims drift.
It was never gated on items 1–10. Those describe experiments this project has not
run; the accepted scope does not require them, and every limitation they concern
is disclosed rather than hidden.

The one substantive constraint publication does impose is on wording. The
narrative is "an evaluation system that detected a confounded result", not "a RAG
system that got better", and the phrasing rules in
[`results.md`](results.md#required-phrasing) govern every public sentence.

Remaining before anything goes out: a GitHub remote, an observed Actions run
(no CI status is claimed until then), and the owner's decision to publish.
