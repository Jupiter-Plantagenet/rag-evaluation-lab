"""Deterministic metrics -- computed without consulting any model.

Reported separately from model-assisted scores throughout, and never blended.
A single "quality score" is exactly what hides a pipeline that improved its
answers by abstaining more often, or improved its citations by citing less.

Every function here is a pure function of a trace record and a case. That means
metrics can be recomputed from stored traces without re-running anything, so a
metric definition can be corrected after the fact and the whole experiment
re-scored -- which is not possible if scoring happens inline and only the
aggregate survives.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from rag_eval.data.spans import is_hit
from rag_eval.types import AbstentionBehaviour, EvalCase

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def _relevant_ranks(case: EvalCase, retrieved: list[dict[str, Any]], threshold: float) -> list[int]:
    """Ranks (1-based) of retrieved chunks that cover any expected evidence span.

    "Covers" means the chunk's character range overlaps the evidence span by at
    least ``threshold`` of the span's length. A chunk in the right document that
    happens to miss the evidence does NOT count -- document-level matching would
    make retrieval look far better than it is on a 14-document corpus, where
    guessing the document is easy and finding the passage is the hard part.
    """
    ranks: list[int] = []
    for r in retrieved:
        chunk_span = (r["char_start"], r["char_end"])
        for ev in case.expected_evidence_spans:
            if ev.doc_id != r["doc_id"] or ev.char_start < 0:
                continue
            if is_hit((ev.char_start, ev.char_end), chunk_span, threshold=threshold):
                ranks.append(r["rank"])
                break
    return sorted(ranks)


def recall_at_k(
    case: EvalCase, retrieved: list[dict[str, Any]], k: int, threshold: float
) -> float | None:
    """Fraction of DISTINCT expected evidence spans covered within the top k.

    Span-level rather than binary hit-rate: a multi-hop case needing three
    documents is not half-answered by finding one, and a binary metric would
    score it identically to a case needing one document.

    Returns None where the case has no expected evidence (the unanswerable
    cases), so that "no evidence required" never averages in as a zero.
    """
    spans = [ev for ev in case.expected_evidence_spans if ev.char_start >= 0]
    if not spans:
        return None

    top = [r for r in retrieved if r["rank"] <= k]
    covered = 0
    for ev in spans:
        for r in top:
            if r["doc_id"] == ev.doc_id and is_hit(
                (ev.char_start, ev.char_end), (r["char_start"], r["char_end"]), threshold=threshold
            ):
                covered += 1
                break
    return covered / len(spans)


def mrr(case: EvalCase, retrieved: list[dict[str, Any]], threshold: float) -> float | None:
    """Reciprocal rank of the FIRST relevant chunk. 0.0 if none retrieved."""
    if not [ev for ev in case.expected_evidence_spans if ev.char_start >= 0]:
        return None
    ranks = _relevant_ranks(case, retrieved, threshold)
    return 1.0 / ranks[0] if ranks else 0.0


def precision_at_k(
    case: EvalCase, retrieved: list[dict[str, Any]], k: int, threshold: float
) -> float | None:
    """Fraction of the top k that are relevant -- the context-noise measure.

    Reported alongside recall rather than instead of it, because they trade off:
    raising k raises recall and lowers precision, and a pipeline that improved
    recall by retrieving more is a different achievement from one that improved
    it by retrieving better.
    """
    if not [ev for ev in case.expected_evidence_spans if ev.char_start >= 0]:
        return None
    top = [r for r in retrieved if r["rank"] <= k]
    if not top:
        return 0.0
    relevant = set(_relevant_ranks(case, retrieved, threshold))
    return sum(1 for r in top if r["rank"] in relevant) / len(top)


def ndcg_at_k(
    case: EvalCase, retrieved: list[dict[str, Any]], k: int, threshold: float
) -> float | None:
    """Deprecated bounded nDCG retained for historical compatibility only.

    Each expected evidence span is one relevance unit and may earn gain once.
    Retrieved chunks are considered in rank order; a chunk that covers one or
    more still-unmatched units is matched to the unit it covers most completely
    (then dataset order breaks ties).  A chunk also earns at most one gain.
    This bounded replacement prevents duplicate gain, but incorrectly limits a
    retrieved chunk containing several independently required spans to one unit.
    Corrected-v2 conclusions therefore do not use this metric.
    """
    spans = [ev for ev in case.expected_evidence_spans if ev.char_start >= 0]
    if not spans:
        return None

    unmatched = set(range(len(spans)))
    matched_ranks: list[int] = []
    for retrieved_chunk in sorted(retrieved, key=lambda r: int(r["rank"])):
        rank = int(retrieved_chunk["rank"])
        if rank > k:
            break
        chunk_span = (retrieved_chunk["char_start"], retrieved_chunk["char_end"])
        candidates: list[tuple[float, int]] = []
        for index in unmatched:
            evidence = spans[index]
            if evidence.doc_id != retrieved_chunk["doc_id"]:
                continue
            if is_hit((evidence.char_start, evidence.char_end), chunk_span, threshold=threshold):
                overlap = max(
                    0,
                    min(evidence.char_end, chunk_span[1]) - max(evidence.char_start, chunk_span[0]),
                )
                coverage = overlap / (evidence.char_end - evidence.char_start)
                candidates.append((coverage, index))
        if candidates:
            _, chosen = max(candidates, key=lambda item: (item[0], -item[1]))
            unmatched.remove(chosen)
            matched_ranks.append(rank)

    dcg = sum(1.0 / math.log2(rank + 1) for rank in matched_ranks)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(spans), k)))
    score = dcg / ideal if ideal > 0 else 0.0
    # This is an invariant of the matching definition, not a clamp.
    assert 0.0 <= score <= 1.0
    return score


def document_recall(case: EvalCase, retrieved: list[dict[str, Any]]) -> float | None:
    """Did we retrieve the right DOCUMENTS, ignoring passage precision?

    Deliberately easier than span recall, and reported next to it. The gap
    between the two separates "looked in the wrong place" from "looked in the
    right place and grabbed the wrong passage" -- two different failure classes
    with two different fixes.
    """
    if not case.expected_document_ids:
        return None
    found = {r["doc_id"] for r in retrieved}
    return sum(1 for d in case.expected_document_ids if d in found) / len(
        case.expected_document_ids
    )


# ---------------------------------------------------------------------------
# Required-fact matching
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)")


def _numbers_in(text: str) -> list[float]:
    out: list[float] = []
    for raw in _NUM_RE.findall(text):
        try:
            out.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return out


def match_fact(answer: str, matcher: dict[str, Any]) -> bool:
    """Evaluate one matcher against an answer. Purely deterministic.

    The numeric matcher parses numbers rather than comparing strings, which is
    what lets an answer be phrased freely while still being checked exactly:
    "2.9%", "2.9 %" and "2.9 per cent" all match, "3%" does not.
    """
    kind = matcher["kind"]

    if kind == "literal":
        needle, hay = matcher["value"], answer
        if not matcher.get("case_sensitive", False):
            needle, hay = needle.lower(), hay.lower()
        return needle in hay

    if kind == "numeric":
        target = float(matcher["value"])
        tol = float(matcher.get("tolerance", 0) or 0)
        # A relative floor, so large values are not held to absolute precision
        # that no natural phrasing would preserve ("about $12,250").
        tol = max(tol, abs(target) * 1e-9)
        return any(abs(n - target) <= tol for n in _numbers_in(answer))

    if kind == "regex":
        flags = re.IGNORECASE if "i" in matcher.get("flags", "i") else 0
        return bool(re.search(matcher["pattern"], answer, flags))

    if kind == "any_of":
        return any(match_fact(answer, m) for m in matcher["matchers"])

    if kind == "all_of":
        return all(match_fact(answer, m) for m in matcher["matchers"])

    if kind == "absent":
        return not match_fact(answer, matcher["matcher"])

    raise ValueError(f"unknown matcher kind: {kind!r}")


def required_fact_coverage(case: EvalCase, answer: str) -> float | None:
    """Weighted fraction of required facts present. None when none are declared."""
    if not case.required_facts:
        return None
    total = sum(f.weight for f in case.required_facts)
    hit = sum(f.weight for f in case.required_facts if match_fact(answer, f.matcher))
    return hit / total if total else None


def forbidden_claim_count(case: EvalCase, answer: str) -> int:
    """How many designed wrong answers appear.

    Matched loosely on the distinctive numeric or quoted token in each entry,
    because the entries are written for a human reader ("$10,000 stated
    unconditionally") rather than as patterns. Reported as a count with that
    imprecision stated, not as a precision-critical metric.
    """
    lowered = answer.lower()
    count = 0
    for claim in case.forbidden_or_unsupported_claims:
        tokens = re.findall(r"\$?\d[\d,]*(?:\.\d+)?%?|[A-Z]{2,}_\d+|T\+\d+", claim)
        if tokens and all(t.lower() in lowered for t in tokens[:1]):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Abstention
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AbstentionOutcome:
    expected: str
    observed: str
    correct: bool


def abstention_outcome(case: EvalCase, abstained: bool, clarified: bool) -> AbstentionOutcome:
    """Three-way, not binary.

    Collapsing "clarify" into "abstain" would score a correct clarification on an
    ambiguous question as a failure -- punishing precisely the behaviour those
    cases exist to reward.

    A clarification on a case that expects a direct answer counts as wrong: the
    corpus supports an answer, and asking instead is unhelpful even though it is
    not incorrect.
    """
    if abstained:
        observed = "abstain"
    elif clarified:
        observed = "clarify"
    else:
        observed = "answer"

    expected = case.expected_abstention_behaviour.value

    # An abstention on an ambiguous case is over-abstention: the corpus HAS the
    # answer, and declining is a worse outcome than surfacing the condition.
    correct = observed == expected
    if (
        expected == AbstentionBehaviour.CLARIFY.value
        and observed == AbstentionBehaviour.ANSWER.value
    ):
        correct = False

    return AbstentionOutcome(expected=expected, observed=observed, correct=correct)


# ---------------------------------------------------------------------------
# Citations
# ---------------------------------------------------------------------------


def citation_metrics(
    case: EvalCase, citations: list[dict[str, Any]], claims: list[dict[str, Any]]
) -> dict[str, Any]:
    """Citation resolution, coverage, and document targeting.

    - validity  : do cited labels resolve to a chunk the model was shown?
    - coverage  : what share of claims carry any citation at all?
    - document precision : of resolved citations, how many point at a document
                  the ground truth actually names?
    The historical ``authoritative`` trace flag is excluded: it cannot establish
    claim-, fact-, or date-specific source authority.
    """
    resolved = [c for c in citations if c["resolved"]]
    fabricated = [c for c in citations if not c["resolved"]]

    expected_docs = set(case.expected_document_ids)
    on_target = [c for c in resolved if c["doc_id"] in expected_docs] if expected_docs else []

    claims_with_citation = {c["claim_id"] for c in citations}
    substantive = [c for c in claims if len(c["text"].split()) >= 4]

    return {
        "n_citations": len(citations),
        "n_resolved": len(resolved),
        "n_fabricated": len(fabricated),
        "citation_validity": (len(resolved) / len(citations)) if citations else None,
        "citation_precision_doc": (len(on_target) / len(resolved))
        if resolved and expected_docs
        else None,
        "claim_citation_coverage": (
            len([c for c in substantive if c["claim_id"] in claims_with_citation])
            / len(substantive)
        )
        if substantive
        else None,
        "distinct_docs_cited": len({c["doc_id"] for c in resolved}),
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def mean_ignoring_none(values: list[float | None]) -> float | None:
    """Average over cases where the metric is defined.

    None means "not applicable to this case", never "scored zero". Treating an
    unanswerable case's undefined recall as 0.0 would drag the retrieval average
    down by a quarter and attribute it to retrieval.
    """
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def bootstrap_ci(
    values: list[float], *, resamples: int = 10000, seed: int = 20260806, alpha: float = 0.05
) -> tuple[float, float] | None:
    """Percentile bootstrap CI for a mean.

    Seeded, so the interval is reproducible. At n=22 these intervals are wide
    and the report leans on that rather than apologising for it: an interval
    spanning zero is reported as "no measurable difference", which is a finding.
    """
    import numpy as np

    clean = [v for v in values if v is not None]
    if len(clean) < 3:
        return None

    rng = np.random.default_rng(seed)
    arr = np.asarray(clean, dtype=float)
    means = rng.choice(arr, size=(resamples, len(arr)), replace=True).mean(axis=1)
    return float(np.percentile(means, 100 * alpha / 2)), float(
        np.percentile(means, 100 * (1 - alpha / 2))
    )
