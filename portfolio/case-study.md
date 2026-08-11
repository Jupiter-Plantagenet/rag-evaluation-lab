# Case study — RAG Evaluation Lab

**An evaluation system that caught a confounded result in my own work.**

The interesting outcome of this project is not that a retrieval change improved a
RAG pipeline. It is that the apparatus I built to measure the change was good
enough to show that the apparent improvement was partly an artefact of giving the
new configuration a larger retrieval and context budget — and that once the budget
was held constant, the evidence for better *ranking* did not survive.

That finding came out of an audit of my own experiment, after the result was
already frozen. It is the thing on this page I would most want a client to read.

---

## 1. Problem

A document-grounded RAG system produces fluent, confident, well-formatted answers.
Some of them are wrong. A confident wrong answer with a plausible citation is
indistinguishable from a correct one at a glance, which means the usual signals —
it runs, it looks good, the stakeholder nodded in the demo — carry no information
about reliability.

The question a team actually needs answered is not "does it work?" but eight
narrower ones:

1. Did retrieval surface the correct evidence?
2. Is the answer correct?
3. Is every material claim grounded in retrieved evidence?
4. Are citations real, and attached to the right claims?
5. Is the answer complete?
6. Does the system abstain when the corpus cannot answer?
7. Did an intervention **measurably** improve anything?
8. Can a confirmed failure be frozen so it cannot come back?

None of these is answerable from a chat transcript.

## 2. Why chatbot demos are insufficient

This project began by auditing a working RAG demo — my own earlier one. From the
outside it looked healthy. From its traces:

| The demo showed | What was actually true |
|---|---|
| Source "citations" under every answer | Scraped first-lines of retrieved chunks. Per-answer, not per-claim. Resolved to nothing. Never verified. |
| Answers grounded in retrieved context | The displayed sources came from a *different retrieval pass* than the one that fed the model. They agreed only by coincidence. |
| A working knowledge base | 11 chunks, so `k=4` returned 36% of the corpus for any query — including off-topic ones, which still rendered four confident "sources". |
| Passing tests and CI | 1 of 7 tests passed; the other six referenced symbols that did not exist. CI had been red since the first commit. |
| A live RAG deployment | The deployed config pinned `DEMO_MODE=true`. It served 14 hard-coded strings. |

Every one of those defects is invisible from the interface and obvious from a
trace. That asymmetry is the entire argument for building the harness rather than
another demo.

## 3. Evaluation design

Two pipelines, one code path. `build_pipeline` branches on configuration *values*
only — there is no `if variant == "improved"` anywhere, and a test enforces it. If
the arms were separate code paths, any measured difference could be an artefact of
an unrelated implementation difference and the comparison would establish nothing.
Sharing one path makes the config diff *be* the experimental manipulation.

Four principles did most of the work:

**Metrics stay separated, never blended.** Retrieval, answer content,
grounding/citation and cost are reported apart. A single "quality score" is
exactly what hides a pipeline that improved its answers by abstaining more, or its
citations by citing less.

**Undefined is not zero.** A metric that does not apply to a case returns `None`.
Scoring an unanswerable question's retrieval recall as 0.0 would drag the average
down and blame retrieval for a corpus gap.

**Running and scoring are separate.** The runner writes traces; every metric is a
pure function of a stored trace. A metric definition can be corrected afterwards
and the whole experiment re-scored with no model calls — which is what made the
later audit possible at all.

**Citations bind to the context the model actually saw.** `pack_context` returns
the prompt text *and* the `{"C1": chunk_id}` map; citations resolve against that
map. The citation and the evidence therefore cannot disagree. A label the model
invents is recorded as fabricated rather than dropped, because dropping it reports
zero.

Comparison uses a **paired bootstrap** — 10,000 resamples, seeded — because both
arms answer the same cases. An interval containing zero is reported as *no
measurable difference*, never as an improvement with a caveat.

## 4. Corpus and dataset

**NovaPay is a synthetic corpus for a fictional payment processor. Every fact in
it is invented and there is no real customer data of any kind.** It was written to
make retrieval non-trivial rather than to be answerable: designed distractors,
multi-hop chains spanning documents, superseded policy versions kept alongside
current ones, controlled ambiguities, and deliberate gaps that give unanswerable
questions a principled basis.

14 documents. A 50-case dataset across seven categories — factual, multi-hop,
aggregation, temporal, ambiguous, citation-stress, unanswerable.

**Split: 28 development / 22 held-out.** The loader physically refuses the
held-out split without an explicit `--final` flag, and every access is appended to
a committed ledger with a reason, timestamp and case count. Two accesses exist,
both after the interventions were frozen. A unit test fails if a third appears. "We
didn't tune on the test set" is therefore checkable rather than asserted.

Ground-truth evidence is stored as **quotes**, and character offsets are derived
at load time. Hand-written offsets rot silently on the first prose edit — they
still point somewhere, just at the wrong text — whereas a quote either resolves or
fails validation loudly.

## 5. Baseline

Deliberately simple and deliberately not crippled: fixed-size 500-character
chunking, dense-only retrieval, `top_k = 4`, single-pass generation. Close to what
a competent first implementation looks like, and close to what the audited
predecessor actually did.

A baseline weakened on purpose makes any improvement look good and establishes
nothing. Every choice here is defensible in isolation; the experiment tests
whether they hold up against a corpus with distractors, multi-hop questions and
real gaps.

Its measured development-split failure profile drove everything that followed: **13
of 18 failures (72%) were retrieval**.

## 6. Proposed improved configuration

Four changes, all targeting the measured failure mass, all chosen before the
held-out split was touched:

1. **Structure-aware chunking** — split on Markdown headings, treat tables as
   atomic, carry the heading path into the context.
2. **Hybrid retrieval** — dense + BM25, fused on rank (RRF, k=60 as published, not
   tuned here).
3. **`top_k` 4 → 8.**
4. **Near-duplicate removal** — a consequence of (3), not an independent idea.

Nothing was added that the failure profile did not demand: no reranker, no query
rewriting, no decomposition. Those are defensible techniques with no evidence here
to justify their cost, and adding them would have made the architecture look
sophisticated while confounding the measurement.

Expected trade-offs were written into the config **before** the run, so they could
not be rationalised afterwards: precision would likely fall because `k` doubled,
prompt cost would roughly double, and more context might dilute the generator's
attention.

## 7. Apparent held-out improvement

The held-out split was read once per arm, after interventions were frozen. Of 22
cases, **20 are retrieval-evaluable** (two unanswerable cases declare no evidence
span, so retrieval recall is undefined for them rather than zero).

| Metric | n | Baseline | Improved | Delta | 95% CI |
|---|---:|---:|---:|---:|:---:|
| MRR | 20 | 0.667 | 0.835 | **+0.168** | [+0.008, +0.339] |
| recall@10 | 20 | 0.692 | 0.883 | **+0.192** | [+0.025, +0.375] |

Two of twelve metrics had intervals excluding zero. The other ten did not, and are
reported as no measurable difference. Read quickly, this is a good result.

## 8. Statistical/audit challenge

After the result was frozen, I audited the reporting code against the stored
per-case values — recomputing every number with a second, independent
implementation of the paired bootstrap rather than re-running the reporting
module.

**All twelve metrics reproduced exactly.** The arithmetic was right. The pairing
was genuinely paired, undefined cases were correctly excluded rather than zeroed,
and the mean of per-case differences equalled the difference of means to 1.5 ×
10⁻¹⁶.

Then the finding that mattered. `recall_at_k` filters the stored retrieval list by
`rank <= k`. If `k` exceeds what an arm actually retrieved, the metric silently
degrades to "everything that arm retrieved":

- **Baseline retrieves at most 4 chunks.**
- **Improved retrieves at most 8.**

So the baseline's recall@5 and recall@10 are *both* recall@4, and **recall@10 was
comparing four chunks against eight**. It is a context/retrieval-budget
comparison, not a fixed-cutoff ranking comparison. MRR is cleaner — it is a
ranking quantity — but not budget-free either: the improved arm has four extra
ranks in which to earn a non-zero reciprocal rank.

The original numbers are not false. They are **confounded by the retrieval
budget**, and they were reported under a label that invites a reader to infer
better ranking.

Other audit findings, none of which required withdrawing the result: 30% of
declared forbidden claims are structurally undetectable by the matcher, so that
count is a lower bound; two dataset inconsistencies understate citation precision
by about 6 points in both arms; and twelve metrics were compared at 95% with no
multiplicity control (under a global null, ~0.6 would exclude zero by chance; two
did).

## 9. Matched-budget result

Recomputed with the cutoff matched to the baseline's budget, using the production
metric functions:

| Held-out, n=20 | Delta | 95% CI | |
|---|---:|:---:|---|
| MRR, as originally reported (≤10) | +0.168 | [+0.008, +0.339] | excludes zero |
| **MRR, matched budget (≤4)** | +0.150 | **[−0.017, +0.321]** | **includes zero** |
| recall@10, as originally reported | +0.192 | [+0.025, +0.375] | excludes zero |
| **recall@4, matched budget** | +0.058 | **[−0.067, +0.200]** | **includes zero** |

**At a matched retrieval budget, neither held-out interval excludes zero.** Two
cases carry the original result — F-04 and F-12, whose first relevant chunk sits
at rank 5–8, where the baseline structurally cannot look.

What can be said: *the improved configuration retrieves the required evidence more
often.* That is true, useful, and was a deliberate design choice. What cannot be
said on this evidence: that it *ranks* better.

## 10. Development-only ablation

The improved arm changed four things at once, which supports a package-level
comparison and nothing about which component earned it. I separated them **on the
development split only**, with no generation calls.

> **DEVELOPMENT SPLIT — EXPLANATORY, NOT HELD-OUT EVIDENCE.** These numbers
> attribute a package-level difference to components. They select nothing: the
> improved arm stays frozen. Six of sixteen cells of a full factorial design were
> run and the components interact, so these are descriptive comparisons, not clean
> main effects.

At a matched `k = 4`, so every column is like-for-like:

| Variant (dev, k=4) | MRR | recall@1 | recall@3 |
|---|---:|---:|---:|
| Baseline | 0.435 | 0.226 | 0.530 |
| **Structure-only** | **0.574** | **0.387** | 0.554 |
| Hybrid-only | 0.399 | 0.214 | 0.470 |
| Structure + hybrid | 0.565 | 0.333 | **0.637** |

Three readings, on development data only:

**Structure-aware chunking did the work.** Alone it moves MRR by +0.140 and
recall@1 by +0.161 — more of the ranking gain than the full four-part bundle
delivers.

**Hybrid retrieval alone made things worse.** It is below baseline on MRR
(0.399 vs 0.435), recall@1 (0.214 vs 0.226) and recall@3 (0.470 vs 0.530). The
config had predicted BM25 would rescue the exact-term cases; on fixed-size chunks
it did not. It pays off only *in combination* with structure-aware chunking — and
even then it raises recall@3 while lowering recall@1 relative to structure alone.
That is an interaction, and it is why the ablation is labelled descriptive.

**Raising `top_k` bought coverage and nothing else.** Isolated at both places it
can be isolated, the budget change moved recall@1 and recall@3 by **exactly
zero**, while improving recall@10 and document recall and costing precision. This
is the audit finding measured directly rather than argued.

Acting on "structure-only beats the full bundle on two metrics" would mean
selecting a configuration using development data with no untouched split left to
test it on. So it was not acted on.

## 11. Failure and trade-off analysis

Failures are classified automatically from trace signals — manual labelling
neither scales nor reproduces. Sixteen classes, ordered by **cause** rather than
severity, so a generation error downstream of a retrieval miss is not
double-counted as an independent defect. The ordering is the methodology: a reader
who disagrees with a classification can point at a rule.

Held-out, the improved configuration **converts total misses into partial misses**:

| Class | Baseline | Improved |
|---|---:|---:|
| retrieval_miss | 4 | **1** |
| retrieval_partial_multihop | 3 | 4 |
| unsupported_claim | 1 | 2 |
| evidence_ranked_low | 2 | 2 |
| ambiguity_collapse | 1 | 1 |

Evidence now enters the candidate window without reliably reaching the top of it —
which is mechanically why rank-sensitive metrics over a wide window moved while
common-cutoff recall did not. Net: **one case fixed** on held-out, against four on
development.

**Trade-offs, reported because a comparison that lists only gains is marketing:**

| | Baseline | Improved | |
|---|---:|---:|---|
| non-authoritative citations | 4 | **7** | worse |
| fabricated citations | 0 | 0 | unchanged |
| forbidden claims | 6 | 6 | unchanged |
| precision@5 (point estimate) | 0.287 | **0.220** | decreased |

Ten of twelve held-out metric intervals contained zero. One case, F-14,
**regressed**. Nine cases fail in both arms, clustered in ambiguity handling,
superseded-policy reasoning and multi-hop aggregation — none of which the
interventions targeted.

The forbidden-claim count is itself a **lower bound**: the matcher keys on numeric
or code-shaped tokens, and 30% of declared forbidden claims contain neither.

This mixed and partly negative picture is the output working correctly. An
evaluation that only ever confirms the change you hoped for is not measuring the
change.

## 12. Regression testing

Five confirmed development-split failures are frozen as offline tests that run
with no API key. Each names its originating case, its measured failure class, why
the assertion is meaningful, and which intervention is expected to preserve it.

Example — **F-15**, "How many dashboard seats do I get on Pro?". The evidence is a
table row, `| Dashboard seats | 3 | 15 | unlimited |`. Under fixed-size chunking
the covering chunk begins *mid-table* and the column header row — the one that
says which number is Starter, which is Pro, which is Enterprise — is in a
different chunk entirely. Three numbers, no labels: exactly the context shape that
produces a confident wrong answer rather than a visible failure. The test asserts
that structure-aware chunking keeps the row with its header.

One test is frozen **because its case still fails**. A-08's retention table became
atomic under the new chunker — the mechanism worked — and the case failed anyway.
Without that test, the chunk-level fix and the case-level outcome blur together
and "structure-aware chunking fixed the A-08 problem" becomes sayable. It did not.

No regression test is derived from a held-out failure. Building one would tune
against the held-out split by the back door — more quietly than a config change,
and just as fatally.

Writing these tests also surfaced a documentation error: the config credited F-07's
fix to a split table header, but the traces show the fixed-size chunk *does*
contain the header. The real mechanism was section scoping. The config comment was
left as written — it is part of the pre-run record, and editing it afterwards is
the retrofitting this project exists to prevent — and the correction is recorded
in the docs and the test.

## 13. Reproducibility

**164 offline tests pass**; 3 local-model parity tests are skipped without the
optional model tier. No API key is needed to install, test, re-score the
experiment or regenerate its reports — scoring is a pure function of stored
traces.

The test suite is offline *by construction*, not by convention: provider keys are
deleted from the environment and `socket.connect` is monkeypatched to raise, so an
attempted network call fails with a traceback pointing at the offending line
instead of succeeding quietly.

The held-out artefacts are **frozen behind SHA-256 checksums**, parsed out of the
document that records them so there is no second copy to drift. A unit test fails
if any frozen file changes. The failure this guards against is not misconduct — it
is someone re-running a command and regenerating an artefact, which looks
identical to an original.

Also: two platform lock files, `torch` deliberately excluded from both (on PyPI's
manylinux wheels it is the CUDA build, which would add ~2.5 GB of `nvidia-*`
wheels to every CI run) with a guard script that fails if it leaks back in;
content-addressed caches keyed on the prompt template hash, so editing a prompt
invalidates its entries rather than silently reusing answers generated from
different instructions; and no cache TTL, because a research cache that expires on
a timer destroys reproducibility on a timer.

**CI status is not claimed.** The workflow's commands pass locally; no GitHub
Actions run has been observed for the current tree.

## 14. Limitations

- **Synthetic corpus, authored by one person.** The distractors, the cases and the
  interventions were designed by the same person. Difficulty was chosen, not
  encountered.
- **50 cases; 22 held out.** One case is worth 4.5 percentage points on any
  held-out proportion. The study is underpowered for anything but large effects.
- **Ten of twelve held-out metrics were inconclusive.** That is the correct answer
  at this n, not a failure of analysis.
- **Category-level counts are tiny** — one to three cases in several categories.
  Those rows are descriptive and cannot support an interval.
- **Single-annotator ground truth.** No inter-annotator agreement figure.
- **One generator, one embedding model, one configuration.** No evidence about how
  any of this behaves elsewhere.
- **The intervention is a bundle**, and the ablation separating it is
  development-only.
- **The arms differ in context budget** — the central caveat of this case study.
- **Citation validity does not imply entailment.** It verifies a citation
  *resolves* to a chunk the model was shown, not that the chunk *supports* the
  claim. Establishing entailment needs model-assisted grading, which is not
  implemented — so no claim here depends on an LLM judge.
- **No multiple-comparison adjustment**, so nothing here is described as
  statistically significant.
- **Cost is unmeasured.** Prompt tokens roughly doubled between arms; the runs used
  a free tier, so the real cost is currently priced at zero.
- **Not production-ready.** No authentication, no threat model, no security review,
  no load testing.

## 15. My role

**A self-directed research-engineering case study.** Not client work; there is no
external stakeholder, no production traffic and no adversarial user.

I did all of it: the architecture and implementation, the synthetic corpus and the
50-case dataset with its ground-truth spans, the evaluation and metric design, the
experimental design and split protocol, the runs, the statistical audit that found
the budget confound, the failure taxonomy, the integration and regression suites,
and the documentation.

The part I would point at is the audit. The confound was in my own frozen result,
found by deliberately attacking work I had already published to myself — and the
response was to constrain what the result may be used to claim rather than to
quietly restate it.

## 16. Deliverables

Produced here, and reusable on comparable work:

- **Evaluation harness** — configuration-driven, two arms sharing one code path,
  runs decoupled from scoring.
- **Retrieval benchmark** — versioned dataset with quote-anchored ground truth, a
  guarded held-out split and an access ledger.
- **Trace instrumentation** — one JSONL record per case carrying retrieved chunk
  IDs and scores, the exact context, parsed claims, resolved citations, tokens,
  latency and errors.
- **Citation and grounding diagnostics** — validity, claim coverage, document
  precision and authority, reported separately because they fail independently.
- **Statistical comparison** — paired bootstrap with explicit, disclosed
  interpretation rules.
- **Failure taxonomy** — sixteen cause-ordered classes, automatic from trace
  signals, unit tested.
- **Regression suite** — confirmed failures frozen as offline tests.
- **Reproducibility package** — locks, seeds, content-addressed caches, checksummed
  frozen artefacts.
- **Findings report** — with an explicit claim boundary and required phrasing.

---

### Read next

- [`docs/results.md`](../docs/results.md) — every measured number and the phrasing it licenses
- [`docs/statistical-audit.md`](../docs/statistical-audit.md) — the audit, including finding A-13
- [`docs/limitations.md`](../docs/limitations.md) — the full boundary
- [`docs/reproduction.md`](../docs/reproduction.md) — how to re-run it
