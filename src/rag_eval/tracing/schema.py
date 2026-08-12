"""The trace record -- one JSONL line per evaluated case.

This shape is simultaneously four things: the on-disk trace format, the data
contract the report reads, the payload the demo UI serves, and the input every
metric consumes. Keeping them one shape rather than four is what stops a number
in the report from disagreeing with the trace it supposedly came from.

The design rule throughout: **record what happened, not a summary of what
happened.** Every retrieval score is kept rather than collapsed to a rank; the
exact context string is kept rather than reconstructed from chunk ids. Current
runs also retain the rendered prompt; frozen historical traces predate that
field being populated and retain question, context, context hash and template
provenance instead.
Diagnosing a failure means answering questions nobody anticipated, and a
summary can only answer the anticipated ones.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rag_eval import TRACE_SCHEMA_VERSION, __version__
from rag_eval.types import PipelineOutput


def _git_state() -> dict[str, Any]:
    """Record the commit AND whether the tree was dirty.

    A run from an uncommitted tree is not reproducible, and saying so in the
    trace is more useful than discovering it months later when the numbers
    cannot be regenerated.
    """
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5
            ).stdout.strip()
        )
        return {"git_sha": sha or "unknown", "git_dirty": dirty}
    except Exception:
        return {"git_sha": "unknown", "git_dirty": None}


def environment_record(seed: int) -> dict[str, Any]:
    import numpy

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "rag_eval_version": __version__,
        "numpy": numpy.__version__,
        "seed": seed,
        **_git_state(),
    }


@dataclass
class TraceRecord:
    """One case, start to finish."""

    # --- provenance ---------------------------------------------------------
    run_id: str
    case_id: str
    pipeline_name: str
    config_hash: str
    pipeline_hash: str
    template_sha: str
    corpus_manifest_sha: str
    dataset_id: str
    split: str
    schema_version: int = TRACE_SCHEMA_VERSION

    # --- input --------------------------------------------------------------
    query: str = ""
    category: str = ""
    answerable: bool = True
    expected_behaviour: str = "answer"

    # --- retrieval ----------------------------------------------------------
    retrieval_kind: str = ""
    top_k: int = 0
    retrieved: list[dict[str, Any]] = field(default_factory=list)
    rewritten_queries: list[str] = field(default_factory=list)

    # --- context and generation --------------------------------------------
    context_labels: dict[str, str] = field(default_factory=dict)
    context_text: str = ""
    context_sha: str = ""
    generator_model: str = ""
    prompt: str = ""
    answer: str = ""
    abstained: bool = False
    clarification_requested: bool = False

    # --- claims and citations ------------------------------------------------
    claims: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    unresolved_labels: list[str] = field(default_factory=list)

    # --- evaluation -----------------------------------------------------------
    metrics: dict[str, Any] = field(default_factory=dict)
    evaluator_outputs: list[dict[str, Any]] = field(default_factory=list)
    failure_classes: list[str] = field(default_factory=list)

    # --- accounting -----------------------------------------------------------
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cache_hit: bool = False
    estimated_cost_usd: float = 0.0

    # --- failures -------------------------------------------------------------
    errors: list[str] = field(default_factory=list)

    started_at: str = ""
    finished_at: str = ""
    environment: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


def record_from_output(
    output: PipelineOutput,
    *,
    run_id: str,
    case: Any,
    pipeline: Any,
    dataset_id: str,
    corpus_manifest_sha: str,
    started_at: str,
) -> TraceRecord:
    from hashlib import sha256

    cfg = pipeline.config
    return TraceRecord(
        run_id=run_id,
        case_id=case.id,
        pipeline_name=cfg.name,
        config_hash=cfg.config_hash,
        pipeline_hash=cfg.pipeline_hash,
        template_sha=pipeline.template_sha,
        corpus_manifest_sha=corpus_manifest_sha,
        dataset_id=dataset_id,
        split=case.split.value,
        query=output.query,
        category=case.category,
        answerable=case.answerable,
        expected_behaviour=case.expected_abstention_behaviour.value,
        retrieval_kind=cfg.retrieval.kind,
        top_k=cfg.retrieval.top_k,
        retrieved=[
            {
                "rank": sc.rank,
                "chunk_id": sc.chunk.chunk_id,
                "doc_id": sc.chunk.doc_id,
                "char_start": sc.chunk.char_start,
                "char_end": sc.chunk.char_end,
                "heading_path": list(sc.chunk.heading_path),
                "score": sc.score,
                "dense_score": sc.dense_score,
                "lexical_score": sc.lexical_score,
                "rrf_score": sc.rrf_score,
                "rerank_score": sc.rerank_score,
            }
            for sc in output.retrieved
        ],
        rewritten_queries=list(output.rewritten_queries),
        context_labels=dict(output.context_labels),
        context_text=output.context_text,
        context_sha=sha256(output.context_text.encode("utf-8")).hexdigest()[:16],
        generator_model=getattr(pipeline.generator, "model", "unknown"),
        prompt=output.raw_prompt,
        answer=output.answer,
        abstained=output.abstained,
        clarification_requested=output.clarification_requested,
        claims=[
            {
                "claim_id": c.claim_id,
                "text": c.text,
                "char_start": c.char_start,
                "char_end": c.char_end,
                "cited_labels": list(c.cited_labels),
            }
            for c in output.claims
        ],
        citations=[
            {
                "citation_id": c.citation_id,
                "claim_id": c.claim_id,
                "label": c.label,
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "source_char_start": c.source_char_start,
                "source_char_end": c.source_char_end,
                "quoted_text": c.quoted_text,
                "resolved": c.resolved,
                "authoritative": c.authoritative,
                "support": c.support,
                "support_score": c.support_score,
            }
            for c in output.citations
        ],
        unresolved_labels=list(output.unresolved_labels),
        prompt_tokens=output.usage.prompt_tokens,
        completion_tokens=output.usage.completion_tokens,
        total_tokens=output.usage.total_tokens,
        latency_ms=output.latency_ms,
        cache_hit=output.cache_hit,
        errors=list(output.errors),
        started_at=started_at,
        finished_at=datetime.now(UTC).isoformat(),
        environment=environment_record(cfg.seed),
    )


class TraceWriter:
    """Append-only JSONL, flushed per record.

    Flushing every line rather than buffering costs a little speed and means a
    run killed halfway still leaves usable traces for every case that completed.
    An evaluation run is long and interruptions are normal; losing the whole
    trace to a Ctrl-C is not an acceptable trade for buffered I/O.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w", encoding="utf-8")
        self.count = 0

    def write(self, record: TraceRecord) -> None:
        self._fh.write(record.to_json() + "\n")
        self._fh.flush()
        self.count += 1

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> TraceWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def read_traces(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line
    ]
