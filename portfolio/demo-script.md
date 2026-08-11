# Demo script — 60–90 seconds

**Not a chatbot conversation.** No one types a question and reads an answer. The
demo shows the *evidence*: one case, its ground truth, what retrieval actually
returned, why it failed, and the test that now holds it in place.

Target: **80 seconds** at an unhurried pace. Screen recording of a terminal and an
editor; no voice-over required, but the narration below is written to be spoken.

**The line the whole thing exists for** — say it at 0:55, and again at the end if
there is room:

> *The important result was not that the improved configuration won. The
> evaluation system showed why the apparent win needed a more careful
> interpretation.*

---

## Beat sheet

| # | Time | On screen | Narration |
|---|---|---|---|
| 1 | 0:00–0:08 | `data/eval/novapay_v1.yaml`, scrolled to **F-15** | "One evaluation case. A question, and what a correct answer has to contain." |
| 2 | 0:08–0:16 | The `expected_evidence_spans` block for F-15 | "Ground truth is a **quote**, not a hand-written offset. Offsets are derived at load time, so if the corpus is edited the case fails loudly instead of pointing at the wrong text." |
| 3 | 0:16–0:28 | `runs/baseline-dev-…/trace.jsonl`, the F-15 record — `retrieved`, then `context_text` | "Here is what retrieval actually returned, and the exact context the model saw. The chunk with the answer row starts **mid-table**. The column header is in a different chunk." |
| 4 | 0:28–0:38 | Same record: `metrics.mrr` = 0.333; highlight `3 \| 15 \| unlimited` in the context | "Three numbers and no labels. Nothing here says which one is Pro. That is how you get a confident, wrong answer — and it is invisible from the chat window." |
| 5 | 0:38–0:46 | `docs/failure-taxonomy.md`, the rule order | "The failure is classified automatically from trace signals. Sixteen classes, ordered by **cause** — retrieval before generation, so one problem is not counted twice." |
| 6 | 0:46–0:55 | `tests/regression/test_frozen_dev_failures.py::test_f15_…`; run `pytest tests/regression -q` | "The confirmed failure is frozen as an offline test: the covering chunk must contain its column header. Runs with no API key." |
| 7 | 0:55–1:05 | `reports/held-out/comparison.md`, MRR and recall@10 rows | "Held-out, 22 cases. MRR 0.667 to 0.835. Recall@10 0.692 to 0.883. Both intervals exclude zero. This looks like a clean win." |
| 8 | 1:05–1:15 | `configs/baseline.yaml` `top_k: 4` beside `configs/improved.yaml` `top_k: 8`; then `docs/statistical-audit.md` finding **A-13** | "But the arms did not retrieve the same amount. Four chunks against eight. `recall_at_k` filters by rank, so above an arm's `top_k` it silently becomes *everything that arm retrieved*." |
| 9 | 1:15–1:25 | The matched-budget table in `docs/results.md` | "Recomputed at a matched budget: MRR +0.150, interval includes zero. Recall@4 +0.058, includes zero. **More retrieved evidence is not proven better ranking.** The original numbers are not false — they are confounded by the budget." |
| 10 | 1:25–1:35 | `pytest` → *164 passed, 3 skipped*; then `python scripts/verify_frozen.py` | "164 offline tests. And the held-out artefacts are checksummed, so if anyone regenerates them the build fails." |

---

## Exact commands

Run these live; each completes fast enough to hold on screen.

```bash
# beat 6
python -m pytest tests/regression -m regression -q

# beat 10
python -m pytest -q
python scripts/verify_frozen.py
```

Expected, and worth showing unedited:

```
11 passed, 3 skipped
164 passed, 3 skipped
all 10 frozen artefacts match their recorded SHA-256 checksums
```

---

## What to say if asked, on camera or after

**"So did it improve the system?"**
It retrieves the required evidence more often. Whether it *ranks* better is not
established on held-out data — at a matched retrieval budget the interval
includes zero.

**"Isn't that a negative result?"**
It is a correct one. Ten of twelve held-out metrics showed no measurable
difference, precision fell, and non-authoritative citations rose from four to
seven. An evaluation that only ever confirms the change you hoped for is not
measuring the change.

**"Why not just fix the budget and re-run?"**
Because the held-out split has been read, and it is frozen. Redesigning against it
now would be tuning on the test set. That work needs a fresh split.

---

## Rules for the recording

- **No chatbot UI.** The moment it looks like a chat demo, it is arguing the
  opposite of the point.
- **Do not crop the trade-offs.** Beat 9 stays on screen long enough to read
  "includes zero" twice.
- **Do not claim CI is green.** No GitHub Actions run has been observed.
- **Say "development split" out loud** whenever ablation numbers appear.
- **Label NovaPay as synthetic** the first time the corpus is on screen — a lower
  third or a visible front-matter line is enough.
- **Never say "statistically significant".** The criterion is that a
  paired-bootstrap 95% CI excluded zero.
