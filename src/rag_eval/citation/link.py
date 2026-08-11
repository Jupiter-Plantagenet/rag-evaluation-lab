"""Claim extraction and claim-to-citation binding.

This module is the project's reason for existing. The predecessor system
attached a flat list of scraped heading strings to each answer, derived from a
*different retrieval pass* than the one that fed the model, resolving to nothing
and verified by nothing. Everything here is a direct response to one of those
defects:

- Citations bind to **claims**, not to answers, so "which part of this is
  supported?" has an answer.
- Labels resolve to **chunk ids and character spans** in a named document, so a
  reader can navigate to the source text.
- A label the model invents is recorded as **unresolved** rather than dropped,
  so fabricated citations are counted instead of hidden.
- Binding uses the **same retrieved set** that produced the context, so the
  citation and the evidence cannot disagree.

Claim segmentation is rule-based, not model-based. An LLM claim-splitter would
put a model inside the measurement of that model's own grounding, and its
failures would be invisible: an atomiser that quietly merges two assertions
makes an ungrounded one disappear. Sentence segmentation is cruder and
occasionally splits awkwardly, but it is inspectable and it fails in the open.
"""

from __future__ import annotations

import re

from rag_eval.types import Citation, Claim, ScoredChunk

# [C1], [C2, C3], [C1][C4] -- tolerated variants of the same intent.
CITATION_RE = re.compile(r"\[(C\d+(?:\s*,\s*C\d+)*)\]", re.IGNORECASE)
LABEL_RE = re.compile(r"C\d+", re.IGNORECASE)

# Abbreviations that must not end a sentence. Short list on purpose: over-eager
# protection merges genuinely separate claims, which hides ungrounded ones.
#
# Each lookbehind INCLUDES the trailing period. The split position is after the
# period, so a lookbehind written as `(?<!\bapprox)` inspects "pprox." and never
# fires -- a bug that made this entire guard inert until a test caught it.
_ABBREV = (
    r"(?<!\bNo\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bvs\.)"
    r"(?<!\bapprox\.)(?<!\bInc\.)(?<!\bLtd\.)(?<!\bcf\.)"
)
SENTENCE_END_RE = re.compile(rf"{_ABBREV}(?<=[.!?])\s+(?=[A-Z0-9$])")


def split_claims(answer: str) -> list[Claim]:
    """Segment an answer into atomic claims, preserving character offsets.

    Offsets are retained so the demo can highlight which span of the answer a
    citation supports, and so a claim can be located in the original text when
    a human reviews a judge's verdict.

    Bullet points are treated as claim boundaries: a list of three fees is three
    assertions, and scoring them as one would let two wrong fees hide behind one
    right one.
    """
    claims: list[Claim] = []
    cursor = 0

    for block in re.split(r"\n\s*\n", answer):
        if not block.strip():
            cursor += len(block) + 2
            continue

        for line in block.split("\n"):
            stripped = line.strip()
            if not stripped:
                cursor += len(line) + 1
                continue

            line_start = answer.find(line, cursor)
            if line_start < 0:
                line_start = cursor

            # A bullet or numbered item is one claim, however many sentences.
            if re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", line):
                claims.append(_make_claim(len(claims), stripped, answer, line_start, line))
            else:
                offset = 0
                for piece in SENTENCE_END_RE.split(line):
                    if piece.strip():
                        start = line.find(piece, offset)
                        claims.append(
                            _make_claim(
                                len(claims),
                                piece.strip(),
                                answer,
                                line_start + max(start, 0),
                                piece,
                            )
                        )
                        offset = max(start, 0) + len(piece)

            cursor = line_start + len(line)

    return claims


def _make_claim(index: int, text: str, answer: str, start: int, raw: str) -> Claim:
    labels = extract_labels(text)
    real_start = answer.find(raw.strip(), max(0, start - 5))
    if real_start < 0:
        real_start = start
    return Claim(
        claim_id=f"cl{index}",
        text=text,
        char_start=real_start,
        char_end=real_start + len(raw.strip()),
        cited_labels=labels,
    )


def extract_labels(text: str) -> tuple[str, ...]:
    """Every [C-n] label in order, deduplicated, upper-cased."""
    found: list[str] = []
    for group in CITATION_RE.findall(text):
        for label in LABEL_RE.findall(group):
            upper = label.upper()
            if upper not in found:
                found.append(upper)
    return tuple(found)


def strip_labels(text: str) -> str:
    """Answer text without citation markers, for display and lexical matching.

    Removing "[C1]" from "$0.30 [C1]." leaves an orphaned space before the
    period. That matters beyond tidiness: this output feeds the lexical
    groundedness checks, where a stray token boundary changes what matches.
    """
    stripped = CITATION_RE.sub("", text)
    stripped = re.sub(r"\s+([.,;:!?)])", r"\1", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


def bind_citations(
    claims: list[Claim],
    context_labels: dict[str, str],
    retrieved: list[ScoredChunk],
    corpus_bodies: dict[str, str],
    authoritative_for: dict[str, set[str]] | None = None,
) -> tuple[list[Citation], list[str]]:
    """Resolve each claim's labels to real source spans.

    Args:
        context_labels: the ``{"C1": chunk_id}`` mapping actually shown to the
            model. Binding against this rather than against a fresh retrieval is
            what guarantees the citation and the evidence cannot disagree.

    Returns:
        (citations, unresolved_labels). A label with no entry in
        ``context_labels`` is a **fabricated citation**: the model produced a
        marker for a source it was never given. It is recorded with
        ``resolved=False`` rather than dropped, because the count of these is a
        headline metric and dropping them would report zero.
    """
    by_id = {sc.chunk.chunk_id: sc for sc in retrieved}
    citations: list[Citation] = []
    unresolved: list[str] = []

    for claim in claims:
        for label in claim.cited_labels:
            chunk_id = context_labels.get(label)
            if chunk_id is None or chunk_id not in by_id:
                unresolved.append(label)
                citations.append(
                    Citation(
                        citation_id=f"ci{len(citations)}",
                        claim_id=claim.claim_id,
                        label=label,
                        chunk_id=None,
                        doc_id=None,
                        source_char_start=None,
                        source_char_end=None,
                        quoted_text=None,
                        resolved=False,
                    )
                )
                continue

            chunk = by_id[chunk_id].chunk
            body = corpus_bodies.get(chunk.doc_id, "")
            quoted = body[chunk.char_start : chunk.char_end] if body else chunk.text

            is_auth = None
            if authoritative_for is not None:
                # None rather than False when we cannot tell: an unknown
                # authority status must not be scored as a known failure.
                owned = authoritative_for.get(chunk.doc_id)
                is_auth = bool(owned) if owned is not None else None

            citations.append(
                Citation(
                    citation_id=f"ci{len(citations)}",
                    claim_id=claim.claim_id,
                    label=label,
                    chunk_id=chunk_id,
                    doc_id=chunk.doc_id,
                    source_char_start=chunk.char_start,
                    source_char_end=chunk.char_end,
                    quoted_text=quoted[:400],
                    resolved=True,
                    authoritative=is_auth,
                )
            )

    return citations, unresolved


# Regexes rather than substrings, after a literal list missed the prompt's own
# canonical refusal: the model wrote "The documentation PROVIDED does not answer
# this question" and the marker "the documentation does not" did not fire. One
# inserted adjective defeated the check.
#
# That near-miss is the argument for the versioning below. This list is a
# measurement instrument, and changing it changes reported abstention rates, so
# it is versioned and any change is a methodology change rather than a tweak.
ABSTENTION_DETECTOR_VERSION = 3

# An abstention is a statement about the SOURCES, not about NovaPay.
#
# Version 2 matched any "does not <verb>" and fired on "NovaPay does not provide
# tax advice, but the rate is 2.9% + $0.30" -- a complete, correct, non-abstaining
# answer that happened to contain a negation about the company. Since NovaPay's
# documentation is full of things NovaPay does not do, that false positive would
# have recurred across the corpus and inflated the measured abstention rate on
# exactly the answerable cases.
#
# So the negation must have a source-referring subject. That is a real semantic
# distinction and not a hack: "the excerpts do not say" is an abstention;
# "NovaPay does not lend" is a fact.
_SOURCE = r"(?:the\s+)?(?:documentation|excerpts?|context|sources?|passages?|documents?|text|information\s+provided|provided\s+\w+)"
_NEG = r"(?:do(?:es)?\s+not|don't|doesn't|fail\s+to|fails\s+to)"
_REPORT = (
    r"(?:contain|include|state|specify|mention|say|answer|cover|provide|address|indicate|detail)"
)

ABSTENTION_PATTERNS = (
    # Source-anchored negation, in either order.
    rf"\b{_SOURCE}\s+(?:\w+\s+){{0,3}}{_NEG}\s+(?:\w+\s+){{0,3}}{_REPORT}\b",
    rf"\b{_NEG}\s+(?:appear\s+)?(?:to\s+be\s+)?{_REPORT}(?:ed)?\s+(?:\w+\s+){{0,2}}(?:in|by)\s+{_SOURCE}\b",
    # Inherently meta -- these are always about the answering process itself and
    # need no subject anchor.
    r"\b(?:cannot|can't|unable\s+to)\s+(?:answer|determine|find|verify)\b",
    r"\b(?:no|insufficient)\s+information\b",
    r"\bi\s+(?:don't|do\s+not)\s+know\b",
    r"\bnot\s+(?:documented|specified|stated|mentioned|covered)\b",
    rf"\bis\s+not\s+(?:in|present\s+in|found\s+in|available\s+in)\s+{_SOURCE}\b",
)

_ABSTENTION_RE = re.compile("|".join(ABSTENTION_PATTERNS), re.IGNORECASE)

CLARIFICATION_MARKERS = (
    "which plan",
    "which region",
    "could you clarify",
    "can you clarify",
    "do you mean",
    "did you mean",
    "depends on",
    "it depends",
    "which did you mean",
    "are you asking",
)


def detect_abstention(answer: str) -> bool:
    """Lexical, versioned, and reported as approximate.

    A pattern list is crude -- it will miss an unusual paraphrase, and it can
    fire on a hedge inside an otherwise complete answer. It is used anyway
    because the alternative is asking a model whether a model abstained, which
    makes the measurement depend on the thing being measured. The judge produces
    an independent abstention verdict, and disagreement between the two is a
    recorded signal rather than something silently resolved in favour of either.

    A known false-positive shape: an answer that gives a full answer and then
    adds "the excerpts do not specify the effective date". That is scored as an
    abstention here and is one of the reasons the two-detector disagreement rate
    is published rather than assumed to be zero.
    """
    return bool(_ABSTENTION_RE.search(strip_labels(answer)))


def detect_clarification(answer: str) -> bool:
    """Did the answer surface a conditionality rather than collapse it?

    Requires an actual question mark alongside a cue, or two distinct cues.
    "It depends on your plan: Starter is $50,000" states the conditionality and
    then answers, which is the behaviour the ambiguous cases reward; a bare
    "depends" with no follow-through is not.
    """
    lowered = strip_labels(answer).lower()
    hits = [m for m in CLARIFICATION_MARKERS if m in lowered]
    return bool(hits) and ("?" in answer or len(hits) >= 2)
