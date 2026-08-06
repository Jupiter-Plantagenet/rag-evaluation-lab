"""Character-span arithmetic -- the coordinate system everything else depends on.

Retrieval scoring, citation resolution, and the source-span viewer in the demo
all reduce to "does this character range overlap that one". Getting this wrong
would not crash anything; it would produce plausible metrics that mean something
other than what they claim, which is why this module is small, explicit, and
heavily tested.
"""

from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")


def normalise_text(text: str) -> str:
    """NFC only -- length-preserving where it matters, and never re-wrapped.

    Deliberately does NOT collapse whitespace: that would shift every offset in
    the corpus and silently invalidate every stored span.
    """
    return unicodedata.normalize("NFC", text)


def resolve_quote(body: str, quote: str) -> tuple[int, int] | None:
    """Locate ``quote`` in ``body`` and return its character span.

    Tries an exact match first. Falls back to a whitespace-insensitive search,
    because Markdown wraps prose at 80 columns and a quote spanning a line break
    is otherwise unmatchable while being perfectly correct ground truth.

    Known limitation: a quote that spans a blockquote continuation (``> `` at the
    start of the following line) will not match, because the marker is content
    rather than whitespace. Authoring guidance is to quote within a single line;
    the dataset validator surfaces any quote that fails to resolve, so this fails
    loudly at authoring time rather than quietly at scoring time.

    Returns None when the quote is absent. Callers must treat that as an error --
    ground truth that cannot be located is not ground truth.
    """
    body = normalise_text(body)
    quote = normalise_text(quote)

    idx = body.find(quote)
    if idx >= 0:
        return idx, idx + len(quote)

    flat_body = _WS.sub(" ", body)
    flat_quote = _WS.sub(" ", quote).strip()
    flat_idx = flat_body.find(flat_quote)
    if flat_idx < 0:
        return None

    start = _map_flat_offset_to_real(body, flat_idx)
    end = _map_flat_offset_to_real(body, flat_idx + len(flat_quote))
    return start, min(end, len(body))


def _map_flat_offset_to_real(body: str, flat_offset: int) -> int:
    """Translate an offset in the whitespace-collapsed body back to the real one."""
    seen = 0
    in_ws = False
    for i, ch in enumerate(body):
        if seen >= flat_offset:
            return i
        if ch.isspace():
            if not in_ws:
                seen += 1
                in_ws = True
        else:
            seen += 1
            in_ws = False
    return len(body)


def spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    """Half-open intervals. Touching endpoints do not overlap."""
    return a[0] < b[1] and b[0] < a[1]


def overlap_length(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def coverage_fraction(evidence: tuple[int, int], retrieved: tuple[int, int]) -> float:
    """How much of ``evidence`` the ``retrieved`` span covers, in [0, 1].

    Directional on purpose. The question retrieval scoring must answer is "did we
    surface the evidence", not "was the chunk tightly scoped" -- a large chunk
    that fully contains a short quote is a retrieval success, whatever its
    precision. Chunk over-breadth is measured separately, as context noise.
    """
    span = evidence[1] - evidence[0]
    if span <= 0:
        return 0.0
    return overlap_length(evidence, retrieved) / span


def is_hit(
    evidence: tuple[int, int],
    retrieved: tuple[int, int],
    *,
    threshold: float = 0.5,
) -> bool:
    """Does a retrieved chunk count as having found this evidence span?

    A threshold is unavoidable: chunk boundaries fall wherever the chunker put
    them, so an evidence quote is frequently split across two chunks and neither
    contains all of it. Requiring full containment would score a correct
    retrieval as a miss purely because of where a boundary landed -- which would
    make the metric a measure of chunk alignment rather than of retrieval.

    The default of 0.5 means "most of the evidence is here". It is a stated
    parameter of the methodology, recorded in every run manifest, and its
    sensitivity is reported rather than assumed.
    """
    return coverage_fraction(evidence, retrieved) >= threshold
