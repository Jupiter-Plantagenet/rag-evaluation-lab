# RAG Evaluation Lab: Grounding, Citations and Regression Testing

An evaluation and regression-testing harness for document-grounded
retrieval-augmented generation.

The deliverable is not a chatbot. It is the apparatus for answering a harder
question about one:

1. Did retrieval surface the correct evidence?
2. Is the answer correct?
3. Is every material claim grounded in retrieved evidence?
4. Are citations real, and attached to the right claims?
5. Is the answer complete?
6. Does the system abstain when the corpus cannot answer?
7. Did an intervention **measurably** improve anything?
8. Can a confirmed failure be frozen so it cannot come back?

> **Status: verification complete; portfolio/publication packaging in progress.**
>
> The experiment is finished and its held-out result is **frozen** — closed
> evidence, protected by checksums a test verifies. A Phase-4 verification pass
> then audited the statistics, built the integration and regression suites, ran a
> development-only ablation, and corrected the public claim boundary. No further
> scientific development is in scope; what remains is packaging.
>
> Questions 1, 3, 5, 6, 7 and 8 are answered by deterministic measurement.
> Questions 2 and 4 are answered only in part — establishing that a citation
> *supports* its claim needs model-assisted grading, which is **not implemented**
> and is a research extension rather than a packaging blocker. See
> [Claim boundary](#claim-boundary).

---

## The result, stated once and precisely

On a held-out split of **22 cases**, the improved retrieval configuration raised
**MRR** from 0.667 to 0.835 (95% paired-bootstrap CI [+0.008, +0.339]) and
**recall@10** from 0.692 to 0.883 (CI [+0.025, +0.375]). Ten of the twelve measured
metrics showed **no measurable difference**.

**Both surviving results depend on the improved arm retrieving twice as many
chunks as the baseline.** At a matched retrieval budget neither interval excludes
zero (MRR +0.150 [−0.017, +0.321]; recall@4 +0.058 [−0.067, +0.200]). The honest
summary is that the improved *configuration* retrieves the required evidence more
often — not that its *ranking* is better.

Costs, reported because a comparison that only lists gains is marketing:
precision@5 fell by 0.068, non-authoritative citations rose from 4 to 7, and
forbidden claims did not fall. Full numbers, and the phrasing they license, in
[`docs/results.md`](docs/results.md).

All metrics are deterministic. No number here depends on an LLM judge.

---

## Why not just show a chatbot demo

A demo answers one question — *does it produce plausible text?* — and hides every
question that matters for reliability. A confident, fluent, well-formatted answer
that cites a document which does not contain the claim looks exactly like a
correct one, until someone checks.

This repository is the checking. Its design comes from auditing a working RAG demo
(this author's own, see [`docs/source-project-audit.md`](docs/source-project-audit.md))
and cataloguing what a demo cannot tell you:

| The demo showed | What was actually true |
|---|---|
| Source "citations" under every answer | Scraped first-lines of retrieved chunks. Per-answer, not per-claim. Resolved to nothing. Never verified. |
| Answers grounded in retrieved context | The displayed sources came from a *different retrieval pass* than the one that fed the model. They agreed only by coincidence. |
| A working knowledge base | 11 chunks, so `k=4` returned 36% of the corpus for any query — including off-topic ones, which still rendered four confident "sources". |
| Passing tests and CI | 1 of 7 tests passed; the other six referenced symbols that did not exist. CI had been red since the first commit. |
| A live RAG deployment | The deployed config pinned `DEMO_MODE=true`. It served 14 hard-coded strings. |

None of that is visible from the outside. All of it is visible from a trace.

---

## What it does

### IMPLEMENTED

- **Two pipelines, one config surface.** A deliberately simple baseline (fixed-size
  chunking, dense-only retrieval, fixed `top-k`, single-pass generation) and an
  improved pipeline. They differ by configuration, not by forked code paths —
  enforced by a test, so "the improvement" cannot quietly become "a different
  program".
- **Separated metrics, never blended.** Retrieval, answer, grounding/citation and
  system cost are reported apart. A single "quality score" is precisely what hides
  a pipeline that improved its answers by abstaining more.
- **Deterministic scoring.** Every published number is settled by lexical, numeric
  span and entity overlap with no model in the loop.
- **Structured traces.** Every case emits one JSONL record with retrieved chunk IDs
  and scores, the exact context the model saw, parsed claims, resolved citations,
  token counts, latency and errors.
- **Citations bound to the context map.** A citation resolves against the same
  `{"C1": chunk_id}` mapping the model was shown, so the citation and the evidence
  cannot disagree. An invented label is recorded as fabricated, not dropped.
- **Paired-bootstrap intervals on every comparison.** 10,000 resamples, seeded. An
  interval containing zero is reported as *no measurable difference*.
- **An honest held-out split.** The loader physically refuses the test split
  without an explicit `--final` flag and logs every access with a reason. Two
  accesses exist. The result is frozen behind SHA-256 checksums that a unit test
  verifies — see [`docs/frozen-held-out-result.md`](docs/frozen-held-out-result.md).
- **Automatic failure classification.** Sixteen classes, ordered by cause, unit
  tested. *(Computed from stored traces; not yet written into the trace records —
  see DEFERRED.)*
- **Regression tests from real failures.** Five confirmed dev-split failures frozen
  as offline tests that run with no API key. Each names its originating case,
  measured failure class, and the intervention expected to preserve it.
- **A dev-only retrieval ablation** separating the four bundled interventions,
  explanatory only.

### PLANNED

- **Model-assisted grading.** Versioned rubrics, recorded judge model and
  parameters, structured rationales, a human-override file, and a published
  grader-agreement figure. `src/rag_eval/judge/` is currently an empty package and
  the `judge_*` config fields are inert.
- **Wiring the failure taxonomy into the runner**, so `failure_classes` is
  populated in traces rather than computed out-of-band.
- **A committed CI replay cache** under `tests/fixtures/cache/`.
- **Cost accounting** against published list prices.

### DEFERRED

- **A second, externally-authored corpus** (SQLite's public documentation, fetched
  and never redistributed) as a check against overfitting to prose the author
  wrote.
- **Demo UI** serving stored traces. `src/rag_eval/demo/` is an empty package.
- **Two known dataset inconsistencies** (audit A-1, A-2), left unfixed because
  fixing them would alter the frozen held-out numbers.

Full list with rationale: [`docs/deferred-work.md`](docs/deferred-work.md).

## Corpus

A synthetic knowledge base for a fictional payment processor, **NovaPay**, built to
make retrieval non-trivial: designed distractors, multi-hop chains, superseded
policy versions kept alongside current ones, controlled ambiguities, and deliberate
gaps that give unanswerable questions a principled basis.

**NovaPay does not exist and every fact in the corpus is invented.** There is no
real customer data of any kind. See
[`data/corpus/novapay/LICENSE`](data/corpus/novapay/LICENSE).

---

## Requirements

Python 3.12. **No API key is required** to install, test, re-score the experiment
or regenerate its reports — scoring is a pure function of stored traces. A key and
the Tier-2 stack (`torch`) are needed only to generate *new* model outputs.

## Quick start

```bash
git clone <repo> && cd rag-evaluation-lab
python -m venv .venv && .venv/Scripts/activate      # Windows
pip install -r requirements/lock/windows-py312.txt  # or linux-py312.txt
pip install -e . --no-deps

pytest                            # 164 passed, 3 skipped — offline, no credentials
python scripts/verify_frozen.py   # frozen held-out artefacts match their checksums
rag-eval ledger                   # held-out split access history
```

Full command reference: [`docs/reproduction.md`](docs/reproduction.md).

---

## Documentation

| | |
|---|---|
| [`results.md`](docs/results.md) | Every measured number, and the phrasing it licenses |
| [`statistical-audit.md`](docs/statistical-audit.md) | Independent recomputation of the frozen report; 13 findings |
| [`frozen-held-out-result.md`](docs/frozen-held-out-result.md) | Checksums, provenance, and the no-tuning constraint |
| [`evaluation-methodology.md`](docs/evaluation-methodology.md) | What is measured and which choices would have flattered it |
| [`architecture.md`](docs/architecture.md) | The five decisions that carry the design |
| [`failure-taxonomy.md`](docs/failure-taxonomy.md) | Sixteen classes, cause-ordered, with measured distributions |
| [`limitations.md`](docs/limitations.md) | The boundary of what this evidence supports |
| [`reproduction.md`](docs/reproduction.md) | Three levels, by what they require |
| [`deferred-work.md`](docs/deferred-work.md) | What was designed and not built |

## Portfolio

Packaging for a public write-up. Nothing has been published.

| | |
|---|---|
| [`case-study.md`](portfolio/case-study.md) | The narrative: an evaluation system that caught a confounded result in its author's own work |
| [`upwork-portfolio-copy.md`](portfolio/upwork-portfolio-copy.md) | Draft portfolio copy, with a wording guard |
| [`demo-script.md`](portfolio/demo-script.md) | 60–90 second walkthrough — evidence, not a chatbot conversation |
| [`publication-checklist.md`](portfolio/publication-checklist.md) | 16 pre-publication checks, executed, with results |
| [`assets/charts/`](assets/charts/) | Four figures, 1600×1200, regenerated by `scripts/make_portfolio_visuals.py` |

The figure generator re-reads `reports/held-out/comparison.json` and
`reports/ablation/dev-retrieval-ablation.json` on every run and **fails** if a
plotted value has drifted, so the visuals cannot silently disagree with the
evidence.

## Reproducibility

- Two platform locks (`requirements/lock/`), the Linux one hash-pinned and
  cross-compiled so CI never resolves dependencies for itself.
- `torch`/`transformers`/`faiss` are deliberately **excluded** from both locks and
  live in `constraints/torch-cpu.txt`. On PyPI's manylinux wheels `torch` is the
  CUDA build, so including it would add ~2.5 GB of `nvidia-*` wheels to every CI
  run. `scripts/assert_ci_env.py` fails the build if any leaks back in.
- Seeded throughout; content-hash caches for embeddings and model responses; corpus
  and dataset checksums recorded in every run manifest.
- The test suite is offline by construction: provider keys are deleted from the
  environment and `socket.connect` is monkeypatched to raise, so an attempted call
  fails with a traceback rather than succeeding quietly.
- On a cache miss while offline the pipeline **fails loudly** rather than falling
  back — a silent fallback would let a green build certify a system that never ran.

**CI status is not claimed here.** The workflow's commands pass locally; no GitHub
Actions run has been observed for the current tree, and a badge will appear only
once one has.

## Claim boundary

Every claim carries three things: **the split it was measured on, the number of
cases behind it, and whether the metric is deterministic or model-assisted.** A
sentence that cannot carry all three is not a claim and does not ship here.
Differences whose confidence interval crosses zero are reported as *no measurable
difference*.

The criterion used throughout is that **the paired-bootstrap 95% CI excluded
zero**. That is not a significance test: there is no null model, no p-value, and no
correction for comparing twelve metrics at once. The phrase "statistically
significant" is not used anywhere in this repository, and the machine-readable
field is named `ci_excludes_zero` for the same reason.

**This is a self-directed case study**, not a paid client deployment. It is
evaluated on a bounded synthetic corpus authored by one person, with one embedding
model and one generation model, on a small held-out set. It is not evidence of
production readiness, and not evidence about LLM-based grading — none was
performed. Citation validity here means a citation *resolves*, not that the cited
passage *entails* the claim.

Words deliberately not used: *enterprise-grade · production-grade · autonomous ·
fully secure · unbiased · comprehensive · universal RAG benchmark · state-of-the-art
· battle-tested · scalable · real-time · human-level · eliminates hallucination ·
statistically significant.* Each is either unmeasurable from this evidence or false
at this scope.

**Not for production use.** There is no authentication, no threat model, no
security review, and no operational hardening.

## Licence

MIT for code ([`LICENSE`](LICENSE)). CC BY 4.0 for the synthetic corpus
([`data/corpus/novapay/LICENSE`](data/corpus/novapay/LICENSE)).
