# Frozen held-out result

> **Historical frozen record.** This document preserves the original held-out
> result as recorded at freeze time. Some metric definitions and interpretations
> were subsequently corrected or withdrawn. For the current conclusions, use the
> [corrected-v2 report](../reports/corrected-v2/held-out/comparison.md) and
> [correction note](corrected-release-v2.md).

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

SHA-256 over the exact bytes **as stored in the repository**, which are LF-normalised
by `.gitattributes`. Any clean checkout on any platform reproduces them.

> **These hashes were re-recorded once, and the artefact content did not change.**
>
> The original values were computed from a Windows working copy in which the
> generated artefacts carried CRLF line endings. Git normalises them to LF on
> commit, so the recorded hashes described bytes that existed only on the author's
> machine and **could not be verified by anyone else** — the first CI run on Ubuntu
> failed on exactly this.
>
> The fix normalised the working copy to the canonical LF form and re-recorded the
> hashes from it. Before overwriting any file, its content was parsed and compared:
> `comparison.json` deserialises to structurally identical data, every JSONL record
> is identical, and every text file is byte-identical once CRLF is mapped to LF. No
> number, no trace record and no ledger entry changed. What changed is the encoding
> of the line terminator, and therefore the hash of the file on disk.
>
> This is a defect in how the freeze was *recorded*, not in what was frozen.

```
f7c2df4ceb322c817e5cc7a6bbf083f9dd471f70172f20a3f01f199e74164352  runs/baseline-test-20260806T182019Z-66ee099b/trace.jsonl
93c8f20dcba3fbfa5756db0ea8d2f6778ba55683c21f34c16c34e185bbf86b35  runs/baseline-test-20260806T182019Z-66ee099b/metrics.json
79d63dd7f83aed0f4d26ca8b6f9412c6ecd779aed416392ecd1742dae428e88e  runs/baseline-test-20260806T182019Z-66ee099b/config.resolved.yaml
1f13b109a811d43d45650850d063c68716dd7741a1150f8eb03fbeff1b2299f8  runs/improved-test-20260806T182251Z-1e6a1bf8/trace.jsonl
8ad4eda6b101982077c03861bd71a188e9a628721b1bbe9c4f854ae5d31ffe0f  runs/improved-test-20260806T182251Z-1e6a1bf8/metrics.json
502634793471474f5a09322fd7850ba665bd73034540206d065e318877e31b79  runs/improved-test-20260806T182251Z-1e6a1bf8/config.resolved.yaml
c73cd8ae9c9ad43eb63f8600069807dbd3211d6e661c3814e7a115153d87d539  reports/held-out/comparison.json
aede4d883a358033508dbe31b4f6b86a69bd8b1eabe6b627ffae034548f7f0b6  reports/held-out/comparison.md
e111d3e862f9c6db94d0fba3c414513a30b06e52bed64052c0de102ba1729f62  reports/held-out/metrics.csv
23ff2dfa3f55818d411e2b1cf9a62b8143918b87699b5aa4a269a6aadf042d35  runs/.test_ledger.jsonl
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
