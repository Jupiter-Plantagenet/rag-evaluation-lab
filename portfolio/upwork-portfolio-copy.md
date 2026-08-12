# Upwork portfolio copy (draft for review)

## Title

**RAG Evaluation & Reliability — Retrieval, Citations, Regression Tests**

## Description

RAG systems can produce plausible answers while failing retrieval, source
attribution, abstention, or regression behaviour. I build evaluation and
reliability tooling that makes those failures measurable and actionable.

I can deliver an evaluation dataset, retrieval benchmark, citation/evidence
diagnostics, trace instrumentation, failure analysis, paired before/after
evaluation, regression suite, and reproducible technical report.

In this case study, a retrieval change initially looked better until evaluation
controlled for the fact that it retrieved twice as much context. The audit
prevented additional context budget from being mistaken for proven ranking
improvement.

Self-directed research-engineering case study using a controlled synthetic
corpus; not a prior client deployment.

## Short version

I build RAG evaluation and reliability tooling: evidence-anchored test sets,
retrieval and citation diagnostics, per-case traces, failure analysis, paired
reports, and regression tests. In this case study, an apparent retrieval win was
reframed after a common-budget audit showed that more context had not established
better held-out ranking.

## Deliverables

- Evaluation datasets and retrieval benchmarks
- Citation-resolution and evidence diagnostics
- Per-case trace instrumentation
- Failure analysis and regression tests
- Paired before/after evaluations
- Reproducible technical reports

Evidence: [corrected results](../reports/corrected-v2/held-out/comparison.md),
[case study](case-study.md), and [limitations](../docs/limitations.md).
