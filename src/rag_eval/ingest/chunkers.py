"""Chunking strategies.

Two chunkers, and the difference between them is one of the interventions the
experiment exists to measure -- so they share an interface and differ only in
where they place boundaries.

The invariant both must satisfy: **every chunk carries character offsets into
its parent document, and ``doc.body[chunk.char_start:chunk.char_end]`` equals
``chunk.text``.** This is what makes a citation resolvable back to a source span
rather than to an opaque id. The predecessor project omitted offsets entirely,
which is why its citations pointed at nothing; a property test asserts the
invariant here so it cannot regress.

Chunk ids are content-addressed (``{doc_id}#{sha1(text)[:8]}``) rather than
sequential or random. Sequential ids shift when a document is edited above them;
random UUIDs -- the predecessor's choice -- change on every rebuild, making two
runs incomparable at chunk level. Content addressing means the same text yields
the same id forever, across configs and machines.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

from rag_eval.types import Chunk, Document


def _chunk_id(doc_id: str, text: str) -> str:
    return f"{doc_id}#{hashlib.sha1(text.encode('utf-8')).hexdigest()[:8]}"


def approx_tokens(text: str) -> int:
    """Cheap token estimate: whitespace words times 1.3.

    Deliberately not tiktoken. The count is used for context budgeting and for
    reporting, not for billing, and a real tokeniser would make chunking depend
    on a model-specific vocabulary -- meaning the baseline and improved
    pipelines could not be compared if either changed model.
    """
    return int(len(text.split()) * 1.3) + 1


class Chunker(Protocol):
    """The seam that lets chunking be a config choice rather than a code path."""

    name: str

    def chunk(self, doc: Document) -> list[Chunk]: ...


class FixedSizeChunker:
    """Fixed-width character windows with overlap. The baseline.

    Deliberately simple, not deliberately broken: this is what a competent
    first implementation looks like, and it is the same strategy the predecessor
    project used. Its weakness is structural blindness -- a heading is separated
    from the content it introduces whenever a boundary happens to fall between
    them, and a Markdown table is split from its header row, leaving cells whose
    meaning depended entirely on column position.
    """

    name = "fixed_size"

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, doc: Document) -> list[Chunk]:
        body = doc.body
        chunks: list[Chunk] = []
        step = self.chunk_size - self.chunk_overlap
        for start in range(0, max(len(body), 1), step):
            end = min(start + self.chunk_size, len(body))
            text = body[start:end]
            if not text.strip():
                continue
            chunks.append(
                Chunk(
                    chunk_id=_chunk_id(doc.doc_id, text),
                    doc_id=doc.doc_id,
                    text=text,
                    char_start=start,
                    char_end=end,
                    heading_path=(),
                    token_count=approx_tokens(text),
                )
            )
            if end >= len(body):
                break
        return chunks


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)


class MarkdownStructureChunker:
    """Split on Markdown headings, keeping each section whole where possible.

    Two properties the fixed-size chunker cannot provide:

    - **Headings stay attached to their content**, so a chunk about payout
      timing says "Payout Schedules" somewhere in it. That matters for retrieval
      (the heading carries the query's vocabulary) and for citation display.
    - **Tables are not split from their header row.** A cell reading "15" is
      meaningless without the column it sits under, and the fixed-size chunker
      separates them roughly whenever a table straddles a boundary.

    Oversized sections are still split, but on paragraph boundaries and with the
    heading path repeated into each piece, so the context is never lost.
    """

    name = "markdown_structure"

    def __init__(self, max_chars: int = 1200, min_chars: int = 120) -> None:
        self.max_chars = max_chars
        self.min_chars = min_chars

    def chunk(self, doc: Document) -> list[Chunk]:
        body = doc.body
        boundaries: list[tuple[int, int, str]] = []  # (offset, level, title)
        for m in HEADING_RE.finditer(body):
            boundaries.append((m.start(), len(m.group(1)), m.group(2)))

        if not boundaries:
            return FixedSizeChunker(self.max_chars, 0).chunk(doc)

        sections: list[tuple[int, int, tuple[str, ...]]] = []
        path: list[str] = []
        for i, (offset, level, title) in enumerate(boundaries):
            path = path[: level - 1]
            while len(path) < level - 1:
                path.append("")
            path.append(title)
            end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(body)
            sections.append((offset, end, tuple(p for p in path if p)))

        chunks: list[Chunk] = []
        for start, end, heading_path in sections:
            text = body[start:end]
            if not text.strip():
                continue

            # Merge a runt section into the next one rather than emitting a chunk
            # that is just a heading. A heading-only chunk matches queries well
            # and answers nothing, which is the worst possible retrieval result.
            if len(text) < self.min_chars and chunks:
                prev = chunks.pop()
                merged = body[prev.char_start : end]
                chunks.append(
                    Chunk(
                        chunk_id=_chunk_id(doc.doc_id, merged),
                        doc_id=doc.doc_id,
                        text=merged,
                        char_start=prev.char_start,
                        char_end=end,
                        heading_path=prev.heading_path,
                        token_count=approx_tokens(merged),
                    )
                )
                continue

            for sub_start, sub_end in self._split_oversized(body, start, end):
                sub_text = body[sub_start:sub_end]
                if not sub_text.strip():
                    continue
                chunks.append(
                    Chunk(
                        chunk_id=_chunk_id(doc.doc_id, sub_text),
                        doc_id=doc.doc_id,
                        text=sub_text,
                        char_start=sub_start,
                        char_end=sub_end,
                        heading_path=heading_path,
                        token_count=approx_tokens(sub_text),
                    )
                )
        return chunks

    def _split_oversized(self, body: str, start: int, end: int) -> list[tuple[int, int]]:
        """Split a long section on blank lines, never inside a table.

        A Markdown table is treated as atomic: splitting one strands data rows
        from the header that gives them meaning, which is precisely the failure
        this chunker exists to avoid.
        """
        if end - start <= self.max_chars:
            return [(start, end)]

        pieces: list[tuple[int, int]] = []
        cursor = start
        while cursor < end:
            limit = min(cursor + self.max_chars, end)
            if limit >= end:
                pieces.append((cursor, end))
                break

            window = body[cursor:limit]
            split_at = window.rfind("\n\n")

            # Do not split inside a table: walk back to before it starts.
            if split_at > 0:
                tail = window[split_at:]
                if "|" in tail and tail.count("|") >= 4:
                    earlier = window[:split_at].rfind("\n\n")
                    if earlier > 0:
                        split_at = earlier

            if split_at <= 0:
                split_at = limit - cursor

            pieces.append((cursor, cursor + split_at))
            cursor += split_at
        return [(s, e) for s, e in pieces if e > s]


def build_chunker(kind: str, **kwargs: object) -> Chunker:
    if kind == "fixed_size":
        return FixedSizeChunker(
            chunk_size=int(kwargs.get("chunk_size", 500)),
            chunk_overlap=int(kwargs.get("chunk_overlap", 50)),
        )
    if kind == "markdown_structure":
        return MarkdownStructureChunker(
            max_chars=int(kwargs.get("max_chars", 1200)),
            min_chars=int(kwargs.get("min_chars", 120)),
        )
    raise ValueError(f"unknown chunker: {kind!r}")
