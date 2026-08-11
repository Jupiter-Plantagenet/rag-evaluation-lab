# Upwork portfolio copy

Ready-to-paste text for a portfolio item. Nothing here has been posted; this is a
draft for review.

Every factual claim below is traceable to [`docs/results.md`](../docs/results.md).
The phrasing rules in
[`results.md`](../docs/results.md#required-phrasing) were applied: no
"statistically significant", no bare percentage improvements, no claim that the
improved configuration ranks better, no client-work framing, no production claim.

---

## A. Title

**RAG Evaluation Lab: Grounding, Citations & Regression Testing**

*(61 characters — comfortably within Upwork's practical title length.)*

Alternates, if a more result-led title is wanted:

- `RAG Evaluation Harness: Retrieval, Citation & Regression Testing` (64)
- `Evaluation-First RAG: Auditing an Apparent Retrieval Improvement` (64)

---

## B. Role

**Research Software Engineer**

---

## C. Short description

*(796 characters)*

> I built an evaluation and regression-testing harness for document-grounded RAG —
> the apparatus that tells you whether a system is actually right, not whether it
> sounds right. It includes a 50-case versioned benchmark over a synthetic corpus,
> a 22-case held-out split that is access-logged and frozen, and separate metrics
> for retrieval, citation quality, abstention behaviour and failure class, with
> paired-bootstrap confidence intervals on every comparison. Confirmed failures
> are frozen into offline regression tests.
>
> The most useful result came from auditing my own experiment: a retrieval change
> that looked like a clear held-out win turned out to be measured against a larger
> retrieval budget. Once the budget was matched, the intervals included zero. The
> harness is what made that visible.

---

## D. Full description

*(1,957 characters)*

> **The problem.** A RAG system that produces confident, well-cited, wrong answers
> looks exactly like one that works. Demos, spot checks and "it runs" tell you
> nothing about grounding, and by the time a user finds the bad answer you have no
> way to tell whether it was retrieval, ranking, context budget or the model.
>
> **What I built.** An evaluation-first RAG harness. Two pipelines — a simple
> baseline and an improved configuration — share one code path and differ only by
> config, so a measured difference is attributable to the change rather than to
> two different programs. Every case emits a structured trace: retrieved chunk IDs
> and scores, the exact context the model saw, parsed claims, citations resolved
> back to character spans in a named document, tokens, latency and errors. Scoring
> is a pure function of those traces, so metrics can be corrected and the whole
> experiment re-scored without re-running a single model call.
>
> **How it was evaluated.** A 50-case dataset over a synthetic 14-document corpus,
> built for difficulty: distractors, multi-hop chains, superseded policy versions,
> deliberate gaps. 28 development cases, 22 held out. The loader refuses the
> held-out split without an explicit flag and logs every access, so "we didn't
> tune on the test set" is checkable rather than asserted. Retrieval, citation,
> abstention and cost metrics are reported separately — never blended into one
> score — with paired-bootstrap intervals.
>
> **What the evaluation revealed.** The improved configuration showed two metrics
> with intervals excluding zero on held-out data. Auditing my own reporting code
> showed both depended on the improved arm retrieving twice as many chunks as the
> baseline; at a matched retrieval budget, both intervals included zero. Ten of
> twelve metrics showed no measurable difference, precision fell, and
> non-authoritative citations rose. The harness caught a confound in my own frozen
> result, which is exactly what it was built to do.

---

## E. My role

**Self-directed research-engineering case study.** Not client work — there is no
external stakeholder, no production traffic and no paid engagement.

Sole author of:

- **Architecture** — configuration-driven pipeline, shared code path across arms,
  runs decoupled from scoring
- **Dataset construction** — 14-document synthetic corpus and 50-case benchmark
  with quote-anchored ground-truth evidence spans
- **Evaluation design** — metric definitions, separation rules, held-out split
  protocol and access ledger
- **Implementation** — ingest, chunking, retrieval, citation binding, tracing,
  metrics, reporting, CLI
- **Experimentation** — baseline and improved runs, failure-profile-driven
  intervention selection, development-only ablation
- **Statistical audit** — independent recomputation of the frozen result; found
  and documented the retrieval-budget confound
- **Regression testing** — confirmed failures frozen as offline tests
- **Documentation** — methodology, results, limitations, reproduction and claim
  boundary

---

## F. Deliverables I can provide on similar work

- **RAG evaluation harness** — configuration-driven, arms sharing one code path
- **Retrieval benchmark** — versioned dataset with quote-anchored ground truth and
  a guarded held-out split
- **Citation and grounding diagnostics** — validity, claim coverage, document
  precision and authority, reported separately
- **Test dataset construction** — including distractors, multi-hop chains and
  principled unanswerable cases
- **Trace instrumentation** — one structured record per case, sufficient to
  diagnose failures nobody anticipated
- **Failure taxonomy** — automatic, cause-ordered classification from trace signals
- **Regression suite** — confirmed failures frozen as offline tests that need no
  API key
- **Reproducibility package** — dependency locks, seeds, content-addressed caches,
  checksummed frozen artefacts
- **Technical findings report** — with an explicit claim boundary and the phrasing
  the evidence licenses

---

## G. Technologies

Only what the repository actually uses:

**Python 3.12** · **NumPy** · **scikit-learn** (TF-IDF + truncated SVD) ·
**PyTorch** and **Hugging Face Transformers** (`all-MiniLM-L6-v2` embeddings) ·
**BM25** (implemented in-repo) · **Reciprocal Rank Fusion** · **Pydantic**
(config validation) · **Jinja2** (prompt templating) · **Google Gemini API**
(`google-genai`) · **pytest** · **ruff** · **mypy** · **GitHub Actions** ·
**YAML/JSON Schema** · **Git**

Not used, and therefore not listed: LangChain, LlamaIndex, FAISS, any vector
database, any orchestration framework.

---

## H. Skill tag suggestions

Upwork's tag vocabulary changes, so these are candidates to search for rather than
guaranteed-available tags. Ordered by relevance:

1. Python
2. Machine Learning
3. Natural Language Processing
4. Retrieval Augmented Generation
5. Artificial Intelligence
6. Model Validation
7. Data Science
8. Technical Documentation

Secondary, if slots remain: Information Retrieval · LLM Evaluation ·
Software Testing · Statistical Analysis · Research

---

## Wording guard

If this copy is edited, these must not creep back in:

| Do not write | Because |
|---|---|
| "improved RAG accuracy by X%" | no bare percentage is supported; the CI is the result |
| "statistically significant" | no null model, no p-value, no multiplicity control |
| "the improved system ranks better" | not established once the budget is matched |
| "hybrid retrieval / BM25 / chunking caused the improvement" | held-out evidence does not attribute to components; the ablation is development-only |
| "production-ready", "enterprise-grade", "scalable" | no security review, no load testing, no threat model |
| "client project", "delivered for" | self-directed case study |
| "CI is green" | no GitHub Actions run has been observed |
