# RAG Evaluation Lab case study

## The client problem this work addresses

A RAG system can look credible while retrieving the wrong passage, attaching an
unresolvable citation, mishandling ambiguity, or reintroducing a known failure.
Evaluation needs evidence and regression controls, not just example answers.

## What was built

RAG Evaluation Lab is a controlled evaluation harness with quote-anchored cases,
span-level retrieval metrics, citation resolution against shown context,
structured traces, failure classification, paired comparisons and offline
regression tests.

The NovaPay case study uses 14 synthetic documents and 50 cases (28 development,
22 held out). The controlled corpus makes every evidence span inspectable and
distributable. Its results are a case-study demonstration, not production
external validation.

## The finding

The improved configuration initially looked stronger on held-out configured
outcomes, but it retrieved 8 chunks while the baseline retrieved 4. At a common
post-hoc budget of 4, MRR was +0.150 with a paired-bootstrap CI of
[-0.017, +0.321], so better held-out ranking was not established.

That was a useful result: the evaluation caught a conclusion that would have
been easy to overstate. Corrected v2 deprecates nDCG and removes the invalid
document-level citation-authority count from public findings.

## Engineering evidence

- Unit, integration and regression tests
- Linux and Windows CI configured
- Ruff and mypy checks
- Corpus and dataset validators
- Immutable held-out artefact checksums
- Corrected trace-only report derivation

## Evidence

[Corrected held-out results](../reports/corrected-v2/held-out/comparison.md) ·
[correction record](../docs/corrected-release-v2.md) ·
[methodology](../docs/evaluation-methodology.md) ·
[limitations](../docs/limitations.md)
