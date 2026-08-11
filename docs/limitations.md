# Limitations

The boundary of what this repository's evidence supports. Every item is a reason a
result here might not hold elsewhere, or might not mean what it appears to mean.

## The corpus and dataset

**The corpus is synthetic and was authored by one person working with an AI
assistant.** Fourteen documents about a fictional payment processor. The
distractors, multi-hop chains, superseded policy pairs and deliberate gaps were
all designed by the same person who then designed the evaluation cases and the
interventions. That is a closed loop: difficulty was chosen, not encountered. A
corpus written by someone else — or a real one, with genuine inconsistency,
duplication and rot — would exercise different failures.

**The dataset is 50 cases.** Seven categories over 50 cases means several
categories have three or four members.

**Ground truth is single-annotator.** No second annotator, no inter-annotator
agreement figure. Where a case is arguable — which of two documents is
authoritative, whether a question is genuinely ambiguous — one person's judgement
is the ground truth and its error rate is unmeasured.

**Two dataset inconsistencies are known and unfixed** (audit A-1, A-2): four
unanswerable cases carry evidence spans but declare no expected documents, and two
held-out cases declare spans in a document absent from their
`expected_document_ids`. Both were left as-is because fixing them would change the
frozen held-out numbers. See [`statistical-audit.md`](statistical-audit.md).

## Sample size

**Only 22 held-out cases.** Ten of twelve metrics returned intervals containing
zero. That is not a defect of the analysis — it is the correct answer at this n —
but it means the study is underpowered for everything except large effects.

**One case is worth 4.5 percentage points** on any held-out proportion. The
abstention "improvement" of 9 points is two cases.

**Category-level n is often very small** — `citation_stress` has one held-out case,
`temporal` two, `ambiguous` two. Per-category rows are printed for completeness
and cannot support an interval. They must not be read as effects.

**No multiple-comparison adjustment.** Twelve metrics at 95%; under a global null
roughly 0.6 would exclude zero by chance. Disclosed rather than corrected, because
the metrics are strongly dependent and Bonferroni would be badly conservative at
this n. No claim on this evidence is licensed to use the phrase "statistically
significant".

## The system under test

**One generator, one configuration.** `gemini-3.1-flash-lite` at temperature 0.
No other model family, size or provider was tried. Nothing here shows how the
harness or the interventions behave with a different generator, and a
retrieval intervention that helps a small model may be irrelevant to a large one.

**One embedding model for the headline runs** (`all-MiniLM-L6-v2`). The
zero-download `tfidf_svd` backend exists so CI can run offline and is genuinely
weaker at paraphrase matching.

**The intervention is a bundle.** Four changes at once. The dev-only ablation
attributes them descriptively — six of sixteen cells, with interacting components
— and that ablation was run on dev, so it says nothing about held-out
generalisation.

**The arms differ in context budget** (`top_k` 4 vs 8). This is audit finding A-13
and it is the most important qualification on this page: both confirmed held-out
results depend on it, and neither interval excludes zero at a matched budget. The
improved configuration retrieves the evidence more often; its *ranking* is not
shown to be better on held-out data.

## What the metrics do not measure

**Citation validity does not imply semantic entailment.** It verifies that a cited
label resolves to a chunk the model was actually shown. It does not verify that
the chunk *supports* the claim attached to it. An answer can score 1.000 on
citation validity while attaching a perfectly resolvable citation to a claim the
cited passage does not support. Establishing entailment needs the judge, which is
not implemented.

**The forbidden-claim count is a lower bound** over a detectable subset. 30% of
declared forbidden claims contain no matchable token and are never counted; the
direction of the bias is unknown.

**Abstention detection is lexical.** It will miss unusual paraphrases and can fire
on a hedge appended to an otherwise complete answer.

**Latency figures are not performance measurements.** `p95` at n=22 is the
second-worst observation, not a percentile estimate, and cached calls replay
stored latency. Both frozen runs report a cache hit rate of 0.0.

**Cost is not measured.** `estimated_cost_usd` is 0.0000 in every record because
the runs used a free tier. Prompt tokens roughly doubled between arms (dev 24.2k →
43.4k), so the cost of the intervention is real and is currently priced at zero.

## Reproducibility

**Model outputs may change if regenerated.** The committed cache replays the exact
responses the frozen runs received. Regenerating them against a provider whose
model has changed — even under the same pinned name — can produce different text,
which would change every answer-side metric. Model versions are pinned to explicit
names rather than `-latest` aliases specifically to reduce this, but a provider can
still change the weights behind a name.

**Reproducing the frozen runs requires torch.** They used MiniLM embeddings, which
CI deliberately does not install. The offline test suite uses `tfidf_svd`, so a
full byte-identical reproduction needs the Tier-2 stack.

**No GitHub Actions run has been observed for this work.** Local CI-equivalent
commands pass; that is a different claim.

## Scope

**Not evidence of production readiness.** No authentication, no threat model, no
security review, no operational hardening, no load testing, no monitoring.

**Not a RAG benchmark.** One synthetic corpus in one domain in one language.

**Not evidence about LLM-based grading**, reliable or otherwise, because none was
performed.

**A self-directed case study**, not a client deployment. There is no external
stakeholder, no production traffic, and no adversarial user.
