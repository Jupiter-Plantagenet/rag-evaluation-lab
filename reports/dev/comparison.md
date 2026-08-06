# Baseline vs improved -- dev split (n=28)

- baseline run: `baseline-dev-20260806T180859Z-66ee099b`
- improved run: `improved-dev-20260806T181347Z-1e6a1bf8`
- generator: `gemini-3.1-flash-lite`
- corpus: `5122d7bf518b0bf6`
- bootstrap: 10,000 paired resamples, seed 20260806

All intervals are 95% paired bootstrap CIs on the per-case difference. **An interval containing zero is reported as no measurable difference, not as an improvement.**

## Deterministic metrics

| Metric | n | Baseline | Improved | Delta | 95% CI | Verdict |
|---|---:|---:|---:|---:|:---:|---|
| recall_at_1 | 28 | 0.226 | 0.333 | +0.107 | [-0.036, +0.250] | no measurable difference |
| recall_at_3 | 28 | 0.530 | 0.637 | +0.107 | [-0.042, +0.262] | no measurable difference |
| recall_at_5 | 28 | 0.530 | 0.649 | +0.119 | [-0.036, +0.280] | no measurable difference |
| recall_at_10 | 28 | 0.530 | 0.738 | +0.208 | [+0.048, +0.375] | **improved** |
| precision_at_5 | 28 | 0.188 | 0.171 | -0.016 | [-0.071, +0.041] | no measurable difference |
| ndcg_at_5 | 28 | 0.437 | 0.531 | +0.093 | [-0.029, +0.221] | no measurable difference |
| mrr | 28 | 0.434 | 0.581 | +0.146 | [+0.027, +0.273] | **improved** |
| document_recall | 25 | 0.840 | 0.933 | +0.093 | [-0.007, +0.207] | no measurable difference |
| required_fact_coverage | 25 | 0.720 | 0.853 | +0.133 | [+0.033, +0.260] | **improved** |
| citation_validity | 21 | 1.000 | 1.000 | +0.000 | [+0.000, +0.000] | no measurable difference |
| citation_precision_doc | 21 | 0.889 | 0.895 | +0.006 | [-0.075, +0.095] | no measurable difference |
| claim_citation_coverage | 28 | 0.712 | 0.811 | +0.099 | [-0.023, +0.241] | no measurable difference |

## Counts (summed over cases, not averaged)

| Counter | Baseline | Improved | Change |
|---|---:|---:|---:|
| n_fabricated | 0 | 0 | +0 |
| n_non_authoritative | 2 | 3 | +1 <- worse |
| forbidden_claims | 6 | 7 | +1 <- worse |

## Abstention behaviour

Accuracy: baseline 0.750, improved 0.893

| expected -> observed | Baseline | Improved |
|---|---:|---:|
| `abstain->abstain` | 3 | 3 |
| `answer->abstain` | 4 | 0 |
| `answer->answer` | 18 | 22 |
| `clarify->abstain` | 1 | 2 |
| `clarify->answer` | 2 | 1 |

## Per category

| Category | n | Base recall@5 | Impr recall@5 | Base facts | Impr facts |
|---|---:|---:|---:|---:|---:|
| aggregation | 4 | 0.375 | 0.500 | 0.500 | 0.750 |
| ambiguous | 3 | 0.500 | 0.500 | 0.667 | 0.667 |
| citation_stress | 2 | 0.167 | 0.167 | 0.500 | 0.667 |
| factual | 9 | 0.778 | 1.000 | 0.889 | 1.000 |
| multi_hop | 6 | 0.417 | 0.556 | 0.667 | 0.833 |
| temporal | 1 | 1.000 | 1.000 | 1.000 | 1.000 |
| unanswerable | 3 | 0.333 | 0.333 | - | - |

Categories with n below about 4 cannot support an interval; their rows are shown for completeness and should not be read as effects.

## Latency

| | p50 ms | p95 ms | mean ms | cache hit rate |
|---|---:|---:|---:|---:|
| baseline | 3730.9 | 16420.6 | 5273.6 | 0.0 |
| improved | 3747.5 | 6326.1 | 4011.2 | 0.0 |

_p95 at this n is the second-worst observation, not a percentile estimate. Cached calls replay stored latency; read alongside cache_hit_rate._
