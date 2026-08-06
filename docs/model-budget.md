# Model selection and quota budget

This project runs on the Gemini free tier. That is a real constraint on the
experiment's shape, so it is recorded here rather than discovered by whoever
tries to reproduce it.

## Measured limits (2026-08-07)

The published rate-limit page no longer lists per-model numbers; it defers to
AI Studio. These were established empirically, by probing until refusal:

| Model | Status | Evidence |
|---|---|---|
| `gemini-2.5-flash` | free-tier daily quota **exhausted** after ~250 requests | 429 `generate_content_free_tier_requests`, still refusing after a 65-second wait, so not a per-minute window |
| `gemini-2.5-flash-lite` | **404 — retired for new users** | "no longer available to new users" |
| `gemini-2.0-flash` | free-tier `limit: 0` | no free allowance remains |
| `gemini-3.1-flash-lite` | available | verified live |
| `gemini-3.5-flash-lite` | available | verified live |
| `gemini-flash-lite-latest` | available | verified live |

Two things worth noting for anyone reproducing this. First, the `retry in 40s`
hint returned alongside a 429 is **not reliable** — it was returned when the
exhausted quota was daily, not per-minute, and following it produces a retry
loop that cannot succeed. Second, daily quotas reset at midnight Pacific.

## What this experiment needs

| Purpose | Calls |
|---|---|
| Generation: baseline over dev (28) + held-out (22) | 50 |
| Generation: improved over dev (28) + held-out (22) | 50 |
| Judging: 2 rubrics x 50 cases x 2 pipelines | 200 |
| **Total** | **300** |

## Allocation

- **Generation: `gemini-3.1-flash-lite`**
- **Judging: `gemini-3.5-flash-lite`**

Both are **pinned to explicit versions, never to a `-latest` alias.** An alias
resolves to different weights over time, which would mean a "reproducible" run
silently producing different output next month — an unusually bad property for a
project whose subject is reproducibility.

### Why the generator changed, and why it does not invalidate the comparison

The first partial run used `gemini-2.5-flash` until its daily quota ran out. The
generator is now `gemini-3.1-flash-lite`.

This does not weaken the experiment. The claim under test is *"these retrieval
interventions improve grounding and citation quality on this corpus, holding the
generator constant"*. The generator is held constant **across the baseline and
improved arms**, which is the comparison that matters. Which generator it is
changes what the numbers describe, not whether the comparison is valid.

What it does change is the scope of the claim, and the report says so: results
describe `gemini-3.1-flash-lite` on this corpus, and nothing is asserted about
how they transfer to a larger model.

The ~19 cached `gemini-2.5-flash` responses remain on disk and are simply
unused — the model id is part of the cache key, so there is no risk of silently
mixing responses from two generators into one result set.

### Why the judge is a different model from the generator

A model judging its own output has a documented self-preference bias. Using
`gemini-3.5-flash-lite` to judge `gemini-3.1-flash-lite` output does not
eliminate that — they are the same family, share training lineage, and a fully
independent judge (a different vendor, or human annotation at scale) was out of
scope here.

It is a **partial mitigation, reported as such.** The honest control is the
grader-agreement figure measured against human labels on a stratified subset,
which is published alongside every model-assisted metric. Deterministic metrics
are unaffected by any of this and are reported separately.

## Practical notes

- The response cache makes quota a **one-time cost per unique prompt**. A
  re-run over already-executed cases makes zero API calls.
- A run that exhausts quota still writes a complete trace file: failed cases
  carry the error and are excluded from metrics rather than silently dropped.
  Re-running fills the gaps, because completed cases are served from cache.
- `RAG_EVAL_OFFLINE=1` forbids live calls entirely and replays from cache. This
  is what CI uses, and what a reviewer without a key should use.
