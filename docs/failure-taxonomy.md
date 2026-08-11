# Failure taxonomy

Every failed case gets exactly one **primary** class, assigned automatically from
signals already in the trace. Manual labelling does not scale and does not
reproduce: two people label differently, and one person labels differently on two
days.

Implementation: `src/rag_eval/evaluation/taxonomy.py`.

## What counts as a failure

A case fails if any of these hold:

- the pipeline raised (`errors` is non-empty)
- the abstention outcome is wrong
- required-fact coverage is below 1.0 (a required fact is *required*)
- recall@5 is below 1.0
- a fabricated citation appears
- a forbidden claim appears

An unanswerable case that correctly abstained has nothing else to fail: its
required-fact coverage and recall are undefined, and letting `None` drag it into
the failure set would count a correct abstention as a defect.

Note the consequence: **the failure set is dominated by retrieval by
construction**, because `recall@5 < 1.0` is a strict criterion that most partial
retrievals trip.

## The ordering is the methodology

Rules are checked in **cause** order, not severity order:

```
0.  pipeline_error                  infrastructure, before anything is interpretable
1.  retrieval_miss                  recall == 0
    retrieval_partial_multihop      0 < recall < 1, multi_hop|aggregation|citation_stress
    evidence_ranked_low             0 < recall < 1, otherwise
2.  failed_abstention               expected abstain, answered
    ambiguity_collapse              expected clarify, did not
    over_abstention                 expected answer, abstained (recall was 1.0)
3.  policy_version_confusion        temporal case with a forbidden claim
4.  citation_unresolvable           a fabricated citation
    citation_non_authoritative      citation_stress case citing a restating doc
5.  unsupported_claim               a forbidden claim
    aggregation_error               coverage < 1, aggregation category
    incomplete_answer               coverage < 1, otherwise
    citation_missing                claim-citation coverage < 0.5
6.  format_violation                failed on a signal no rule covers
```

Retrieval is checked before generation because **a generation error downstream of
a retrieval miss is not an independent defect**. Counting both would double-count
one problem and make the taxonomy add up to more failures than there were.

The ordering is stated here, tested, and reported alongside the counts, so a
reader can disagree with a classification by disagreeing with a *rule* rather than
with a judgement call.

### The visible consequence, stated because it looks like an inconsistency

The taxonomy and the abstention table in the same report count different things.
On the dev baseline there are **7 abstention errors** but only **1** is filed as a
behavioural class. The other six occurred on cases that *also* missed evidence, so
cause-ordering files them under retrieval.

Both numbers are correct. They answer different questions: "how often was the
answer/abstain decision wrong?" and "what is the earliest cause in the chain?" A
reader comparing 7 against 1 is not looking at a bug.

## Classes

All sixteen appear in every report, including at zero. Pruning empty rows is how a
taxonomy quietly becomes a highlight reel — and a zero row records that a failure
mode was *looked for*.

| Class | Meaning |
|---|---|
| `retrieval_miss` | No chunk covering any expected evidence span was retrieved. |
| `retrieval_partial_multihop` | Some but not all expected spans were retrieved. |
| `evidence_ranked_low` | Evidence retrieved but ranked below the context cut-off. |
| `retrieval_distractor` | A designed distractor was retrieved while evidence was missed. |
| `policy_version_confusion` | A superseded value used, or a superseded document cited as current. |
| `aggregation_error` | All evidence retrieved; the arithmetic or set reasoning is wrong. |
| `incomplete_answer` | Correct as far as it goes, but a required fact is missing. |
| `unsupported_claim` | A forbidden or unsupported claim appears in the answer. |
| `failed_abstention` | Answered a question the corpus cannot answer. |
| `over_abstention` | Abstained although the evidence was present and retrieved. |
| `ambiguity_collapse` | Picked one reading of an ambiguous question without flagging it. |
| `citation_missing` | Substantive claims carry no citation. |
| `citation_unresolvable` | A cited label maps to no chunk the model was shown. |
| `citation_non_authoritative` | Cited a restating document when an authoritative one exists. |
| `format_violation` | Output violated the response contract. |
| `pipeline_error` | The pipeline raised before producing an answer. |

## Measured distribution

### Dev, n = 28 — failures 18 → 14

| Class | Baseline | Improved |
|---|---:|---:|
| retrieval_miss | 8 | 6 |
| retrieval_partial_multihop | 5 | 3 |
| unsupported_claim | 2 | 2 |
| evidence_ranked_low | 1 | 1 |
| policy_version_confusion | 1 | 1 |
| ambiguity_collapse | 1 | 1 |

### Held-out, n = 22 — failures 11 → 10

| Class | Baseline | Improved | Change |
|---|---:|---:|---:|
| retrieval_miss | 4 | 1 | −3 |
| retrieval_partial_multihop | 3 | 4 | +1 |
| evidence_ranked_low | 2 | 2 | 0 |
| unsupported_claim | 1 | 2 | +1 |
| ambiguity_collapse | 1 | 1 | 0 |

**Ten of sixteen classes never fired on either split.** Some are genuinely absent
(no pipeline errors, no fabricated citations). Others are close to unreachable
given the cause ordering — `over_abstention` requires recall to be exactly 1.0
before it can be considered at all. A class that cannot fire is not evidence that
the failure mode does not occur.

### What moved, and what it means

The improved configuration **converts total misses into partial misses**:
`retrieval_miss` −3, `retrieval_partial_multihop` +1, `unsupported_claim` +1.
Evidence enters the candidate window without reliably reaching the top of it,
which is mechanically why rank-sensitive metrics over a wide window moved while
common-cutoff recall did not.

Net one case fixed on held-out, against four on dev.

**F-14 regressed** on held-out (`ok` → `unsupported_claim`).

**Nine cases fail in both arms** on held-out: A-05, A-07 (aggregation), B-02, B-05
(ambiguous), F-04 (factual), M-04, M-08 (multi-hop), T-02, T-03 (temporal). The
residue is generation-side and ranking-side; none of it was targeted.

## A correction to `configs/improved.yaml`

The improved config explains **F-07** as the table header being split from the
evidence row by fixed-size chunking. The traces do not support that: under
fixed-size chunking the covering chunk *does* contain `| Plan | Limit |`. What it
lacks is any heading path, and it opens with unrelated prose about `403 Forbidden`
and key restriction, so the rate-limit numbers sit inside a chunk that is mostly
about permissions.

The mechanism that fixed F-07 is **section scoping**, not header preservation.
**F-15** is the genuine header-boundary case: its covering chunk begins mid-table
at `0.30 | negotiated |` with the column header row in a different chunk entirely,
so `3 | 15 | unlimited` arrives unlabelled.

Both are frozen as regression tests with this correction recorded in the test
docstrings. The config comment is left as written — it is part of the pre-run
record, and editing it after the fact would be exactly the kind of quiet
retrofitting this repository exists to make impossible.

## Status

The taxonomy is implemented and tested, and the distributions above were produced
from the committed traces. It is **not yet wired into the runner**: `TraceRecord`
has a `failure_classes` field and it is empty in all four committed runs. Wiring
it is [deferred work](deferred-work.md).
