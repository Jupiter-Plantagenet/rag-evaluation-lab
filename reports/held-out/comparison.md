# Baseline vs improved -- test split (n=22)

- baseline run: `baseline-test-20260806T182019Z-66ee099b`
- improved run: `improved-test-20260806T182251Z-1e6a1bf8`
- generator: `gemini-3.1-flash-lite`
- corpus: `5122d7bf518b0bf6`
- bootstrap: 10,000 paired resamples, seed 20260806

All intervals are 95% paired bootstrap CIs on the per-case difference. **An interval containing zero is reported as no measurable difference, not as an improvement.**

## Deterministic metrics

| Metric | n | Baseline | Improved | Delta | 95% CI | Verdict |
|---|---:|---:|---:|---:|:---:|---|
| recall_at_1 | 20 | 0.408 | 0.525 | +0.117 | [-0.058, +0.292] | no measurable difference |
| recall_at_3 | 20 | 0.592 | 0.750 | +0.158 | [-0.008, +0.350] | no measurable difference |
| recall_at_5 | 20 | 0.692 | 0.800 | +0.108 | [-0.042, +0.275] | no measurable difference |
| recall_at_10 | 20 | 0.692 | 0.883 | +0.192 | [+0.025, +0.375] | **improved** |
| precision_at_5 | 20 | 0.287 | 0.220 | -0.068 | [-0.163, +0.013] | no measurable difference |
| ndcg_at_5 | 20 | 0.630 | 0.694 | +0.064 | [-0.088, +0.209] | no measurable difference |
| mrr | 20 | 0.667 | 0.835 | +0.168 | [+0.007, +0.339] | **improved** |
| document_recall | 19 | 0.921 | 0.947 | +0.026 | [+0.000, +0.079] | no measurable difference |
| required_fact_coverage | 19 | 0.789 | 0.895 | +0.105 | [-0.079, +0.289] | no measurable difference |
| citation_validity | 16 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] | no measurable difference |
| citation_precision_doc | 16 | 0.875 | 0.838 | -0.037 | [-0.146, +0.067] | no measurable difference |
| claim_citation_coverage | 22 | 0.701 | 0.754 | +0.054 | [-0.104, +0.223] | no measurable difference |

## Counts (summed over cases, not averaged)

| Counter | Baseline | Improved | Change |
|---|---:|---:|---:|
| n_fabricated | 0 | 0 | +0 |
| n_non_authoritative | 4 | 7 | +3 <- worse |
| forbidden_claims | 6 | 6 | +0 |

## Abstention behaviour

Accuracy: baseline 0.818, improved 0.909

| expected -> observed | Baseline | Improved |
|---|---:|---:|
| `abstain->abstain` | 3 | 3 |
| `answer->abstain` | 3 | 1 |
| `answer->answer` | 14 | 16 |
| `clarify->answer` | 1 | 1 |
| `clarify->clarify` | 1 | 1 |

## Per category

| Category | n | Base recall@5 | Impr recall@5 | Base facts | Impr facts |
|---|---:|---:|---:|---:|---:|
| aggregation | 4 | 0.917 | 0.792 | 0.875 | 0.750 |
| ambiguous | 2 | 0.500 | 1.000 | 1.000 | 1.000 |
| citation_stress | 1 | 1.000 | 1.000 | 1.000 | 1.000 |
| factual | 7 | 0.714 | 0.857 | 0.714 | 1.000 |
| multi_hop | 3 | 0.333 | 0.667 | 0.667 | 0.667 |
| temporal | 2 | 0.583 | 0.417 | 0.750 | 1.000 |
| unanswerable | 3 | 1.000 | 1.000 | - | - |

Categories with n below about 4 cannot support an interval; their rows are shown for completeness and should not be read as effects.

## Latency

| | p50 ms | p95 ms | mean ms | cache hit rate |
|---|---:|---:|---:|---:|
| baseline | 3902.6 | 19302.9 | 5902.8 | 0.0 |
| improved | 3800.6 | 12906.0 | 5485.3 | 0.0 |

_p95 at this n is the second-worst observation, not a percentile estimate. Cached calls replay stored latency; read alongside cache_hit_rate._
