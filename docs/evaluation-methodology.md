# Evaluation methodology

What is measured, how, and which choices would have flattered the result.

## Design

Two arms over the same cases, differing only in retrieval configuration. The
generator, prompt template and seed are inherited unchanged by the improved arm,
so a measured difference cannot be explained by a prompt edit made at the same
time. That controls one confound; it is not on its own an attribution claim, and
audit finding A-13 is the case in point.

| | Baseline | Improved |
|---|---|---|
| chunking | fixed_size, 500 chars, 50 overlap | markdown_structure |
| retrieval | dense only | hybrid dense + BM25, RRF (k=60) |
| top_k | 4 | 8 |
| dedupe | no | yes, 0.8 overlap |
| generator | gemini-3.1-flash-lite, T=0 | *identical* |
| prompt | answer_with_citations.jinja | *identical* |

The improved arm's four changes were chosen **after** the baseline dev run, from
its measured failure distribution: 13 of 18 dev failures (72%) were retrieval, so
all four interventions target retrieval.

## Splits

50 cases: **dev 28**, **held-out 22**. The loader physically refuses the test
split without an explicit `allow_test=True` / `--final`, and every access is
appended to `runs/.test_ledger.jsonl` with a reason, host, timestamp and case
count. Two accesses exist, both after the interventions were frozen at `b0d4fa4`.

"We didn't tune on the test set" is therefore checkable rather than asserted. The
ledger is committed, and a unit test fails if it grows.

## Metrics, and the tempting wrong answer for each

**Retrieval recall is span-level, not a binary hit-rate.** A multi-hop case needing
three spans is not answered by finding one; a binary metric would score it
identically to a single-span case.

**A chunk in the right document that misses the evidence is not a hit.** Document
recall is reported *separately*. The gap between the two separates "looked in the
wrong place" from "looked in the right place and grabbed the wrong passage" — two
failures with two different fixes.

**A chunk counts as covering a span if it overlaps ≥ 50% of the span's length.**
Requiring full containment would score correct retrievals as misses purely because
of where a chunk boundary fell. The threshold is a stated methodology parameter,
recorded in every run manifest.

**Undefined metrics return `None`, never `0.0`.** Treating an unanswerable case's
undefined recall as zero would drag the retrieval average down and attribute the
loss to retrieval.

**Numeric fact matchers parse numbers rather than compare strings**, so "2.9%",
"2.9 %" and "2.9 per cent" all match while "3%" does not.

**Citation quality is four metrics, not one** — validity, claim coverage, document
precision, authority — because they fail independently and have different fixes. A
pipeline can have perfect validity with no coverage (cites correctly, once), or
full coverage with poor authority (cites everything, often the wrong document).

**Nothing is blended into a single quality score.** A single score is exactly what
hides a pipeline that improved its answers by abstaining more, or improved its
citations by citing less.

**Abstention is three-way, not binary.** `clarify` exists because an ambiguous
question *has* an answer in the corpus, often several, and the correct response
surfaces the conditionality rather than declining. Folding it into `abstain` would
score a correct clarification as a failure.

### Known measurement limits

- **`forbidden_claim_count` is a lower bound.** It matches on an extracted numeric
  or code-shaped token; 20 of 67 declared forbidden claims (30%) contain neither
  and are never counted. Audit finding A-3.
- **Abstention detection is lexical and versioned** (`ABSTENTION_DETECTOR_VERSION`).
  It will miss an unusual paraphrase and can fire on a hedge inside an otherwise
  complete answer. Changing the pattern list changes reported abstention rates, so
  it is treated as a methodology change rather than a tweak.
- **Citation validity checks resolution, not entailment.** It verifies that a label
  points at a chunk the model was shown. It does **not** verify that the chunk
  supports the claim. That requires the judge, which is not implemented.

## Statistics

**Paired bootstrap**, 10,000 resamples, seed 20260806, 95% percentile interval on
the per-case difference. Both arms answer the same cases, so the per-case
difference is the unit of analysis; treating the arms as independent would discard
the pairing and widen every interval beyond what the design warrants.

Metrics are compared only over cases where **both** arms defined them, so a case
scored by one arm and skipped by the other cannot silently change which case set a
label refers to.

**An interval containing zero is reported as "no measurable difference"**, never as
an improvement with a caveat.

**The criterion is not a significance test.** There is no null model, no p-value
and no multiple-comparison control across the twelve metrics. The machine-readable
field is called `ci_excludes_zero` for that reason. Expected false exclusions under
a global null are stated inline in every generated report.

**Rank-sensitive metrics are confounded with the retrieval budget** when the arms
have different `top_k`. See [`results.md`](results.md#the-budget-caveat) and audit
finding A-13. This was discovered during the Phase-4 audit, after the held-out
result was frozen; it changes how the result must be described, not the result.

## Failure classification

Automatic, from trace signals — manual labelling neither scales nor reproduces.
Rules are ordered by **cause**, not severity. See
[`failure-taxonomy.md`](failure-taxonomy.md).

## Model-assisted grading

**Not implemented.** No result in this repository depends on an LLM judge. The
config carries `judge_enabled` and `judge_model` fields and
`src/rag_eval/judge/` is an empty package; the fields are inert.

Everything the README once promised about rubrics, human overrides and a published
grader-agreement figure is [deferred work](deferred-work.md), not shipped
behaviour.

## What would have flattered the result, and was not done

- Reporting only dev numbers, where four findings exclude zero instead of two.
- Reporting recall@10 without disclosing that the arms retrieve different amounts.
- Blending metrics into one score, where the precision and authority regressions
  would vanish.
- Dropping the unanswerable cases, which would raise every retrieval average.
- Treating `document_recall`'s `[+0.000, +0.079]` as a near-miss improvement.
- Excluding cases that errored (there were none, but the runner is built so that
  excluding them would be visible rather than convenient).
