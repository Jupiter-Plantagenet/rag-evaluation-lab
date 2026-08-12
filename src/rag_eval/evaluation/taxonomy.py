"""Automatic failure classification from trace signals.

Manual labelling of every failure does not scale and does not reproduce: two
people label differently, and one person labels differently on two days. So
classification is an ordered rule set over signals already present in the trace,
producing one **primary** class per failed case plus optional secondary tags.

Rules are ordered by CAUSE, not by severity. Retrieval failures are checked
before generation failures because a generation error downstream of a retrieval
miss is not an independent defect -- reporting both would double-count one
problem and make the taxonomy add up to more failures than there were.

The ordering is the methodology. It is stated here, tested, and reported
alongside the counts, so a reader can disagree with a classification by
disagreeing with a rule rather than with a judgement call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag_eval.types import EvalCase

# Every class, defined once. All appear in the report even at zero -- pruning
# empty rows is how a taxonomy quietly becomes a highlight reel.
FAILURE_CLASSES: dict[str, str] = {
    "retrieval_miss": "No chunk covering any expected evidence span was retrieved.",
    "retrieval_partial_multihop": "Some but not all expected evidence spans were retrieved.",
    "evidence_ranked_low": "Evidence was retrieved but ranked below the context cut-off.",
    "retrieval_distractor": "A designed distractor was retrieved while expected evidence was missed.",
    "policy_version_confusion": "A superseded value was used, or a superseded document cited as current.",
    "aggregation_error": "All evidence was retrieved; the arithmetic or set reasoning is wrong.",
    "incomplete_answer": "Correct as far as it goes, but a required fact is missing.",
    "unsupported_claim": "A forbidden or unsupported claim appears in the answer.",
    "failed_abstention": "Answered a question the corpus cannot answer.",
    "over_abstention": "Abstained although the evidence was present and retrieved.",
    "ambiguity_collapse": "Picked one reading of an ambiguous question without flagging it.",
    "citation_missing": "Substantive claims carry no citation.",
    "citation_unresolvable": "A cited label maps to no chunk the model was shown.",
    "format_violation": "Output violated the response contract.",
    "pipeline_error": "The pipeline raised before producing an answer.",
}


@dataclass
class Classification:
    case_id: str
    failed: bool
    primary: str | None = None
    secondary: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


def _is_failure(record: dict[str, Any], case: EvalCase, thresholds: dict[str, Any]) -> bool:
    """Whether a case counts as failed at all.

    Deliberately generous about what counts as success on abstention cases:
    abstaining correctly IS the right answer, and required-fact coverage is
    undefined there, so it must not drag them into the failure set.
    """
    if record.get("errors"):
        return True
    m = record.get("metrics", {})

    if not m.get("abstention_correct", True):
        return True

    # An unanswerable case that correctly abstained has nothing else to fail.
    if not case.answerable:
        return False

    coverage = m.get("required_fact_coverage")
    if coverage is not None and coverage < thresholds["min_fact_coverage"]:
        return True
    recall = m.get(f"recall_at_{thresholds['k']}")
    if recall is not None and recall < 1.0:
        return True
    if m.get("n_fabricated", 0) > 0:
        return True
    return bool(m.get("forbidden_claims", 0) > 0)


def classify(
    record: dict[str, Any], case: EvalCase, *, k: int = 5, min_fact_coverage: float = 0.999
) -> Classification:
    """Assign one primary failure class from trace signals.

    ``min_fact_coverage`` defaults to effectively 1.0: a required fact is
    required. Partial coverage is ``incomplete_answer``, which is a distinct
    class from being wrong.
    """
    thresholds = {"k": k, "min_fact_coverage": min_fact_coverage}
    if not _is_failure(record, case, thresholds):
        return Classification(case_id=case.id, failed=False)

    m = record.get("metrics", {})
    secondary: list[str] = []
    evidence: dict[str, Any] = {}

    # --- 0. infrastructure, before anything is interpretable -----------------
    if record.get("errors"):
        return Classification(case.id, True, "pipeline_error", [], {"errors": record["errors"]})

    recall = m.get(f"recall_at_{k}")
    retrieved_docs = {r["doc_id"] for r in record.get("retrieved", [])}
    expected_docs = set(case.expected_document_ids)

    # --- 1. retrieval, before generation -------------------------------------
    # A generation error downstream of a retrieval miss is not an independent
    # defect; classifying it as one would double-count a single problem.
    if recall is not None and recall <= 0.0:
        primary = "retrieval_miss"
        if expected_docs and not (expected_docs & retrieved_docs):
            evidence["retrieved_wrong_documents"] = sorted(retrieved_docs - expected_docs)
            if retrieved_docs:
                secondary.append("retrieval_distractor")
        return Classification(case.id, True, primary, secondary, evidence)

    if recall is not None and 0.0 < recall < 1.0:
        evidence["recall"] = recall
        evidence["missing_documents"] = sorted(expected_docs - retrieved_docs)
        primary = (
            "retrieval_partial_multihop"
            if case.category in {"multi_hop", "aggregation", "citation_stress"}
            else "evidence_ranked_low"
        )
        return Classification(case.id, True, primary, secondary, evidence)

    # --- 2. behaviour: answered when it should not have, or vice versa -------
    observed = m.get("abstention_observed")
    expected = m.get("abstention_expected")
    if observed != expected:
        if expected == "abstain" and observed != "abstain":
            return Classification(
                case.id, True, "failed_abstention", secondary, {"gap_id": case.gap_id}
            )
        if expected == "clarify":
            return Classification(
                case.id, True, "ambiguity_collapse", secondary, {"observed": observed}
            )
        if expected == "answer" and observed == "abstain":
            # Evidence was retrieved (recall == 1.0 to reach here), so this is
            # over-abstention rather than an honest inability to answer.
            return Classification(case.id, True, "over_abstention", secondary, {"recall": recall})

    # --- 3. version confusion, before generic unsupported-claim --------------
    # Checked earlier because using a superseded value is a specific, diagnosable
    # cause; folding it into "unsupported claim" would lose the diagnosis.
    if case.category == "temporal" and m.get("forbidden_claims", 0) > 0:
        return Classification(case.id, True, "policy_version_confusion", secondary, {})

    # --- 4. citation integrity ------------------------------------------------
    if m.get("n_fabricated", 0) > 0:
        return Classification(
            case.id,
            True,
            "citation_unresolvable",
            secondary,
            {"unresolved": record.get("unresolved_labels", [])},
        )

    coverage = m.get("required_fact_coverage")

    claim_coverage = m.get("claim_citation_coverage")
    if claim_coverage is not None and claim_coverage < 0.5:
        secondary.append("citation_missing")

    # --- 5. answer content ----------------------------------------------------
    if m.get("forbidden_claims", 0) > 0:
        return Classification(case.id, True, "unsupported_claim", secondary, {"coverage": coverage})

    if coverage is not None and coverage < 1.0:
        primary = "aggregation_error" if case.category == "aggregation" else "incomplete_answer"
        return Classification(case.id, True, primary, secondary, {"coverage": coverage})

    if claim_coverage is not None and claim_coverage < 0.5:
        return Classification(case.id, True, "citation_missing", [], {"coverage": claim_coverage})

    # Reached only if _is_failure fired on a signal no rule covers -- which is
    # itself worth surfacing rather than silently returning "not failed".
    return Classification(case.id, True, "format_violation", secondary, {"unmatched": True})


def classify_run(
    records: list[dict[str, Any]], cases: dict[str, EvalCase], *, k: int = 5
) -> list[Classification]:
    return [classify(r, cases[r["case_id"]], k=k) for r in records if r["case_id"] in cases]


def taxonomy_counts(classifications: list[Classification]) -> dict[str, int]:
    """Counts for EVERY class, including zeros.

    Zero rows are kept deliberately: a taxonomy that only lists what happened
    reads as a highlight reel and hides which failure modes were looked for and
    not found.
    """
    counts = dict.fromkeys(FAILURE_CLASSES, 0)
    for c in classifications:
        if c.failed and c.primary:
            counts[c.primary] = counts.get(c.primary, 0) + 1
    return counts
