# RAG Evaluation Lab: Grounding, Citations and Regression Testing

An evaluation and regression-testing harness for document-grounded retrieval-augmented generation.

The deliverable is not a chatbot. It is the apparatus for answering a harder question about one:

1. Did retrieval surface the correct evidence?
2. Is the answer correct?
3. Is every material claim grounded in retrieved evidence?
4. Are citations real, and attached to the right claims?
5. Is the answer complete?
6. Does the system abstain when the corpus cannot answer?
7. Did an intervention **measurably** improve anything?
8. Can a confirmed failure be frozen so it cannot come back?

> **Status: in progress.** Phase 0 of 4 complete (audit, scaffold, toolchain).
> No results have been generated yet, so this README contains no metrics. It will
> not contain any until the experiment has actually run — see
> [Claims](#claims-and-their-boundary).

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

- **Two pipelines, one config surface.** A deliberately simple baseline (fixed-size
  chunking, dense-only retrieval, fixed `top-k`, single-pass generation) and an
  improved pipeline. They differ by configuration, not by forked code paths — enforced
  by a test, so "the improvement" cannot quietly become "a different program".
- **Separated metrics, never blended.** Retrieval, answer, grounding/citation and
  system cost are reported apart. A single "quality score" is precisely what hides
  a pipeline that improved its answers by abstaining more.
- **Deterministic first.** Most grounding verdicts are settled by lexical, numeric
  and entity overlap with no model in the loop. Only the residue reaches a judge.
- **Model-assisted grading, bounded and disclosed.** Versioned rubrics, recorded
  judge model and parameters, structured rationales, a human-override file that
  re-runs respect, and a published grader-agreement figure. LLM grading is treated
  as a measurement with error, not as ground truth.
- **Structured traces.** Every case emits one JSONL record with retrieved chunk IDs
  and scores, the exact context the model saw, parsed claims, resolved citations,
  token counts, latency, evaluator outputs and errors.
- **Regression tests from real failures.** Confirmed failures are frozen into tests
  that run offline, with no API key, in CI.
- **An honest held-out split.** The dataset loader physically refuses the test split
  without an explicit `--final` flag and logs every access, so "we didn't tune on
  the test set" is checkable rather than asserted.

## Corpus

A synthetic knowledge base for a fictional payment processor, **NovaPay**, built to
make retrieval non-trivial: designed distractors, multi-hop chains, superseded policy
versions kept alongside current ones, controlled ambiguities, and deliberate gaps that
give unanswerable questions a principled basis.

**NovaPay does not exist and every fact in the corpus is invented.** There is no real
customer data of any kind. See [`data/corpus/novapay/LICENSE`](data/corpus/novapay/LICENSE).

An optional second corpus (SQLite's public-domain documentation) is *fetched*, never
redistributed, to check that the harness is not overfitted to prose the author wrote.

---

## Requirements

Python 3.12. No API key is required to install, test, or run the offline evaluation —
keys are needed only to generate *new* model outputs, and existing results replay from
a committed response cache.

## Quick start

```bash
git clone <repo> && cd rag-evaluation-lab
python -m venv .venv && .venv/Scripts/activate      # Windows
pip install -r requirements/lock/windows-py312.txt  # or linux-py312.txt
pip install -e . --no-deps
pytest                                              # offline, no credentials
```

Command reference lands with Phase 1. Every command in this README is executed
verbatim before it is documented.

---

## Reproducibility

- Two platform locks (`requirements/lock/`), the Linux one hash-pinned and
  cross-compiled so CI never resolves dependencies for itself.
- `torch`/`transformers`/`faiss` are deliberately **excluded** from both locks and
  live in `constraints/torch-cpu.txt`. On PyPI's manylinux wheels `torch` is the CUDA
  build, so including it would add ~2.5 GB of `nvidia-*` wheels to every CI run.
  `scripts/assert_ci_env.py` fails the build if any of them leaks back in.
- Seeded throughout; content-hash caches for embeddings, model responses and judge
  verdicts; corpus and dataset checksums recorded in every run manifest.
- CI runs fully offline. On a cache miss it **fails loudly** rather than skipping —
  a skipped test produces a green badge that certifies nothing.

## Claims and their boundary

Every claim in this repository carries three things: **the split it was measured on,
the number of cases behind it, and whether the metric is deterministic or
model-assisted.** A sentence that cannot carry all three is not a claim and does not
ship here. Differences whose confidence interval crosses zero are reported as *no
measurable difference*, not as improvements.

**This is a self-directed case study**, not a paid client deployment. It is evaluated
on a bounded synthetic corpus with one embedding model and one generation model, on a
small held-out set. It is not evidence of production readiness, and not evidence that
LLM-based grading is reliable.

Words deliberately not used here: *enterprise-grade · production-grade · autonomous ·
fully secure · unbiased · comprehensive · universal RAG benchmark · state-of-the-art ·
battle-tested · scalable · real-time · human-level · eliminates hallucination.* Each is
either unmeasurable from this evidence or false at this scope. Where one would have
been convenient, a specific measured statement appears instead.

**Not for production use.** There is no authentication, no threat model, no security
review, and no operational hardening. The demo UI binds to loopback only and refuses
to start otherwise.

## Licence

MIT for code ([`LICENSE`](LICENSE)). CC BY 4.0 for the synthetic corpus
([`data/corpus/novapay/LICENSE`](data/corpus/novapay/LICENSE)). The fetched public
corpus retains its upstream terms, recorded in `docs/corpora.md`.
