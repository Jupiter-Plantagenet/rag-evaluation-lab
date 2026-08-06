"""Core value types.

All frozen. Immutability matters more than usual here: these objects flow from
retrieval through generation into the trace record and then into metrics, and a
mutation anywhere in that chain would make the trace a record of something other
than what actually ran.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AbstentionBehaviour(str, Enum):
    """What a case expects.

    Three values, not two. CLARIFY exists because an ambiguous question *has* an
    answer in the corpus -- often several -- and the correct response surfaces
    the conditionality rather than declining. Folding it into ABSTAIN would score
    a correct clarification as a failure.
    """

    ANSWER = "answer"
    ABSTAIN = "abstain"
    CLARIFY = "clarify"


class Split(str, Enum):
    DEV = "dev"
    TEST = "test"


@dataclass(frozen=True, slots=True)
class Document:
    """A corpus document, with its body byte-exact as authored.

    ``body`` is never normalised in place. Evidence spans are character offsets
    into exactly these characters, so any normalisation must happen downstream on
    a copy or every offset in the dataset silently shifts.
    """

    doc_id: str
    title: str
    body: str
    front_matter: dict[str, Any]
    sha256: str

    @property
    def authoritative_for(self) -> tuple[str, ...]:
        return tuple(self.front_matter.get("authoritative_for") or ())

    @property
    def is_superseded(self) -> bool:
        return str(self.front_matter.get("status", "")).upper() == "SUPERSEDED"


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrievable unit, carrying the offsets that make citations resolvable.

    ``char_start``/``char_end`` index into the parent Document's body. This is
    the single most important property in the system: without it a citation can
    only name a chunk, and a chunk id means nothing to a reader and nothing
    across chunking configurations. The predecessor project omitted these, which
    is why its citations resolved to nothing.
    """

    chunk_id: str
    doc_id: str
    text: str
    char_start: int
    char_end: int
    heading_path: tuple[str, ...] = ()
    token_count: int = 0

    def __post_init__(self) -> None:
        if self.char_start < 0 or self.char_end < self.char_start:
            raise ValueError(f"{self.chunk_id}: invalid span [{self.char_start}, {self.char_end})")


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    """A chunk with the scores that produced its rank.

    Every score is retained rather than collapsed to a final number, because
    diagnosing a retrieval failure requires knowing *which* retriever surfaced a
    chunk and which one buried it. A single fused score cannot answer that.
    """

    chunk: Chunk
    rank: int
    score: float
    dense_score: float | None = None
    lexical_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None
    rank_before_rerank: int | None = None


@dataclass(frozen=True, slots=True)
class Citation:
    """A claim-level citation, resolved back to a source span.

    ``resolved`` is False when the model emitted a label that maps to no chunk in
    the context it was given. That is a fabricated citation, and counting it is
    the whole point of tracking citations per claim rather than per answer.
    """

    citation_id: str
    claim_id: str
    label: str
    chunk_id: str | None
    doc_id: str | None
    source_char_start: int | None
    source_char_end: int | None
    quoted_text: str | None
    resolved: bool
    authoritative: bool | None = None
    support: str | None = None
    support_score: float | None = None
    verifier: str | None = None


@dataclass(frozen=True, slots=True)
class Claim:
    """One atomic assertion extracted from an answer."""

    claim_id: str
    text: str
    char_start: int
    char_end: int
    cited_labels: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.prompt_tokens + other.prompt_tokens,
            self.completion_tokens + other.completion_tokens,
            self.total_tokens + other.total_tokens,
        )


@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    usage: Usage
    model: str
    finish_reason: str
    latency_ms: float
    cache_hit: bool
    raw_prompt: str = ""


@dataclass(frozen=True, slots=True)
class EvidenceSpan:
    """Ground-truth evidence, anchored to a source document.

    Offsets are derived from ``quote`` at load time rather than stored in the
    dataset. Hand-written offsets rot silently on the first prose edit -- they
    still point somewhere, just at the wrong text -- whereas a quote either
    resolves or fails validation loudly.
    """

    doc_id: str
    quote: str
    char_start: int
    char_end: int
    heading_path: tuple[str, ...] = ()
    authoritative: bool = True


@dataclass(frozen=True, slots=True)
class RequiredFact:
    fact_id: str
    matcher: dict[str, Any]
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    category: str
    question: str
    answerable: bool
    expected_abstention_behaviour: AbstentionBehaviour
    split: Split
    reference_answer: str | None = None
    required_facts: tuple[RequiredFact, ...] = ()
    acceptable_answer_notes: str = ""
    expected_document_ids: tuple[str, ...] = ()
    expected_evidence_spans: tuple[EvidenceSpan, ...] = ()
    forbidden_or_unsupported_claims: tuple[str, ...] = ()
    scoring_notes: str = ""
    source_chain_id: str | None = None
    gap_id: str | None = None


@dataclass(frozen=True, slots=True)
class PipelineOutput:
    """Everything one pipeline invocation produced.

    Carries the retrieved chunks and the exact context string as well as the
    answer, because an answer without the evidence that produced it cannot be
    scored for grounding -- only for plausibility, which is what a demo measures.
    """

    query: str
    answer: str
    retrieved: tuple[ScoredChunk, ...]
    context_text: str
    context_labels: dict[str, str]
    claims: tuple[Claim, ...]
    citations: tuple[Citation, ...]
    abstained: bool
    clarification_requested: bool
    usage: Usage
    latency_ms: float
    cache_hit: bool
    rewritten_queries: tuple[str, ...] = ()
    unresolved_labels: tuple[str, ...] = ()
    errors: tuple[str, ...] = field(default_factory=tuple)
