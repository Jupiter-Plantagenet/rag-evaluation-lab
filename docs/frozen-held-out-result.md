# Frozen held-out result

The held-out evaluation is **closed evidence**. This file exists so that any later
reader — including the author — can prove the numbers were not adjusted after they
were seen.

> **Binding constraint.** No later development work may tune the baseline or the
> improved pipeline against the results recorded here. Neither the retrieval
> configuration, the chunker, the prompt, the generator, nor any metric definition
> may be changed *because of* what the held-out split showed. Work that follows this
> freeze is designed and measured on the **dev** split only. If a change to a metric
> definition is ever justified, it must be published as a **new report version**
> alongside these files, never as an edit to them.

## Provenance

| | |
|---|---|
| Commit at which interventions were frozen | `b0d4fa4` |
| Commit recording the final held-out result | `f4ac2b1` |
| `git_sha` stamped inside the run traces | `b0d4fa4` |
| Dataset | `novapay_v1` |
| Corpus manifest SHA-256 | `5122d7bf518b0bf60d7925384edad8ca3725f01c0566e31ea85e713500451a34` |
| Generator model | `gemini-3.1-flash-lite` |
| Held-out cases | **22** |
| Errors in either arm | 0 |
| Bootstrap | 10,000 paired resamples, seed `20260806`, 95% percentile interval |
| Hit-coverage threshold | 0.5 |

The traces carry `git_sha = b0d4fa4` because that is the code state that *produced*
them; `f4ac2b1` is the commit that *recorded* them. The two differing is expected and
is not evidence of tampering.

### Arm configuration hashes

| Arm | Run ID | `pipeline_hash` | `config_hash` | Chunks indexed |
|---|---|---|---|---|
| baseline | `baseline-test-20260806T182019Z-66ee099b` | `66ee099bcb76` | `9872160eb297` | 164 |
| improved | `improved-test-20260806T182251Z-1e6a1bf8` | `1e6a1bf838ee` | `1411e6c481b4` | 136 |

## Checksums

SHA-256 over the exact bytes as committed at `f4ac2b1`.

```
1b3434bb6437d122a13d6e66559d9d7c9c488642364950ecd91c4e36c36fe680  runs/baseline-test-20260806T182019Z-66ee099b/trace.jsonl
6b8d3b9ab5c32dbe1aa501d213e1032ad6415933f29c0477d489972a8a867721  runs/baseline-test-20260806T182019Z-66ee099b/metrics.json
3255e5057efbc0dbf204c3fc471c3c707776f912ec8bc8528bd3398e0a078883  runs/baseline-test-20260806T182019Z-66ee099b/config.resolved.yaml
ed3a067a248851cd2044cf1f1aaa500e9830506fa33519800edb16cafb73c72c  runs/improved-test-20260806T182251Z-1e6a1bf8/trace.jsonl
29ac452bbc04970d0eef088b592ef852382e86d3e5e3d4509c4328e30cf71891  runs/improved-test-20260806T182251Z-1e6a1bf8/metrics.json
9810ecf9dfa6a476b99ace4b532547165d8fd44b80c3de03cfc73342cfad87b7  runs/improved-test-20260806T182251Z-1e6a1bf8/config.resolved.yaml
5389bbc201963e2922f560795be63f425ddd731a677da5b5705eb2f47b71cf21  reports/held-out/comparison.json
233d5a558cbfde614691a79470b42d638719014a9ab2f30ce9e81d3c1b7ac842  reports/held-out/comparison.md
3f17c1e0bd9067dbc0d6a1d1a4d93feeee6a081951530313cd89e1f6e2e03c9a  reports/held-out/metrics.csv
e3a408feae391cdf6733d43ba25d43690fc50b061a316a8f96623bb3eaf8370d  runs/.test_ledger.jsonl
```

Verify with:

```bash
python scripts/verify_frozen.py
```

The verifier is also a unit test (`tests/unit/test_frozen_artefacts.py`), so an
accidental regeneration fails the build rather than passing silently.

> **Note on the field rename.** After this freeze, the machine-readable comparison
> field `significant` was renamed `ci_excludes_zero` (see
> [`statistical-audit.md`](statistical-audit.md)). The frozen artefacts above retain
> the **old** field name, because renaming it in place would have altered bytes that
> this file exists to protect. Newly generated reports use the new name. The values
> are identical; only the label changed.

## Test-split access ledger

Exactly **two** accesses have ever been recorded, both after the interventions were
frozen at `b0d4fa4`:

| Timestamp (UTC) | Cases | CI | Reason |
|---|---:|---|---|
| 2026-08-06T18:20:19Z | 22 | no | final held-out evaluation, baseline arm; interventions were frozen after the dev-split analysis in commit b0d4fa4 |
| 2026-08-06T18:22:51Z | 22 | no | final held-out evaluation, improved arm; same frozen configuration as the dev analysis |

Later offline analysis of these traces (failure classification, the statistical audit,
and the sensitivity checks in this document) reads the **stored trace files**, not the
dataset split, and therefore adds no ledger entry. `load_all_cases` is the path used
for that work; it does not log, and it must never be used to obtain cases for a run.

## Cases entering each metric

All 22 cases appear in both arms. Metrics are compared only over cases where **both**
arms defined the metric, so every `n` below is a paired count.

| Metric | n | Excluded cases | Why |
|---|---:|---|---|
| `recall_at_{1,3,5,10}`, `precision_at_5`, `ndcg_at_5`, `mrr` | 20 | U-03, U-04 | Unanswerable, no expected evidence span. Retrieval recall is undefined, not zero. |
| `document_recall` | 19 | U-03, U-04, U-06 | No `expected_document_ids`. |
| `required_fact_coverage` | 19 | U-03, U-04, U-06 | No `required_facts` declared. |
| `citation_validity` | 16 | U-03, U-04, U-06, A-07, F-04, F-12 | The three unanswerable cases abstained and emitted no citations; A-07, F-04 and F-12 produced no citations in at least one arm. Validity over zero citations is undefined. |
| `citation_precision_doc` | 16 | same six | Same reason. |
| `claim_citation_coverage` | 22 | — | Defined for every case, including abstentions, which do carry claims. |

**U-06 is scored for retrieval recall but not for document recall.** It is
unanswerable and declares no `expected_document_ids`, yet it carries one
non-authoritative `expected_evidence_span`. Retrieval recall is therefore defined
(and equals 1.000 in *both* arms), while document recall is not. This is recorded as
finding **A-1** in the statistical audit. Its effect on the frozen result is
conservative — a tied pair pulls the paired mean difference toward zero — and the
published verdicts are unchanged when it is removed:

| Metric | As reported (n=20) | Excluding unanswerable (n=19) | Verdict changes? |
|---|---|---|---|
| recall@1 | +0.117 [−0.058, +0.292] | +0.123 [−0.070, +0.307] | no |
| recall@3 | +0.158 [−0.008, +0.350] | +0.167 [−0.009, +0.368] | no |
| recall@5 | +0.108 [−0.042, +0.275] | +0.114 [−0.044, +0.289] | no |
| recall@10 | +0.192 [+0.025, +0.375] | +0.202 [+0.026, +0.395] | no |
| MRR | +0.168 [+0.007, +0.339] | +0.177 [+0.004, +0.360] | no |
| nDCG@5 | +0.064 [−0.088, +0.209] | +0.067 [−0.089, +0.219] | no |
| precision@5 | −0.068 [−0.162, +0.013] | −0.068 [−0.166, +0.018] | no |

This sensitivity analysis is **not** a re-issued result. The frozen report stands as
published; the table above exists to show that its two confirmed findings do not
depend on a scoring edge case.

## What is frozen, precisely

Frozen (must not be regenerated or overwritten):

- both held-out run directories listed above, in full
- `reports/held-out/comparison.json`, `comparison.md`, `metrics.csv`
- `runs/.test_ledger.jsonl`

Not frozen (may be regenerated from stored traces, deterministically, with no model
calls):

- `reports/dev/*` and both dev run directories
- any new analysis written to a *new* path

Re-running the held-out split requires explicit authorisation from the repository
owner and would append a third ledger entry, which is visible to any reader.
