"""Run a pipeline over a split, emit traces, and score deterministically.

Two properties matter more than anything else here:

1. **A failing case still produces a trace.** An exception is caught, recorded
   in the record's ``errors``, and the run continues. A run that aborts on case
   17 of 28 tells you nothing about cases 18-28, and the temptation is then to
   quietly exclude the failure -- which is how a metric silently becomes an
   average over the cases that happened to work.

2. **Scoring is separate from running.** ``score_traces`` is a pure function of
   stored traces, so a metric definition can be corrected afterwards and the
   whole experiment re-scored with no model calls. If scoring happened inline
   and only the aggregate survived, every definition change would cost a rerun.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from rag_eval.config import PipelineConfig
from rag_eval.data.loader import load_cases
from rag_eval.evaluation import (
    metrics as M,  # noqa: N812 - M.<metric> reads better at every call site
)
from rag_eval.pipeline import Pipeline
from rag_eval.tracing.schema import TraceRecord, TraceWriter, record_from_output
from rag_eval.types import EvalCase, Split


def make_run_id(config: PipelineConfig, split: Split) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{config.name}-{split.value}-{stamp}-{config.pipeline_hash[:8]}"


def score_record(
    record: TraceRecord, case: EvalCase, threshold: float, ks: list[int]
) -> dict[str, Any]:
    """Deterministic metrics for one case. No model is consulted."""
    retrieved = record.retrieved
    out: dict[str, Any] = {}

    for k in ks:
        out[f"recall_at_{k}"] = M.recall_at_k(case, retrieved, k, threshold)
        out[f"precision_at_{k}"] = M.precision_at_k(case, retrieved, k, threshold)
        out[f"ndcg_at_{k}"] = M.ndcg_at_k(case, retrieved, k, threshold)
    out["mrr"] = M.mrr(case, retrieved, threshold)
    out["document_recall"] = M.document_recall(case, retrieved)

    out["required_fact_coverage"] = M.required_fact_coverage(case, record.answer)
    out["forbidden_claims"] = M.forbidden_claim_count(case, record.answer)

    outcome = M.abstention_outcome(case, record.abstained, record.clarification_requested)
    out["abstention_expected"] = outcome.expected
    out["abstention_observed"] = outcome.observed
    out["abstention_correct"] = outcome.correct

    out.update(M.citation_metrics(case, record.citations, record.claims))
    out["n_claims"] = len(record.claims)
    return out


def run_split(
    pipeline: Pipeline,
    dataset_path: Path,
    *,
    split: Split,
    allow_test: bool = False,
    reason: str = "unspecified",
    out_dir: Path,
    repo_root: Path,
    limit: int | None = None,
) -> dict[str, Any]:
    corpus_bodies = pipeline.corpus.bodies()
    cases = load_cases(
        dataset_path,
        split=split,
        allow_test=allow_test,
        reason=reason,
        corpus=corpus_bodies,
        repo_root=repo_root,
    )
    if limit:
        cases = list(cases)[:limit]

    cfg = pipeline.config
    run_id = make_run_id(cfg, split)
    run_dir = Path(out_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "config.resolved.yaml").write_text(
        yaml.safe_dump(cfg.model_dump(), sort_keys=True), encoding="utf-8"
    )

    threshold = cfg.evaluation.hit_coverage_threshold
    ks = cfg.evaluation.recall_at_k
    records: list[TraceRecord] = []
    started_wall = time.perf_counter()

    with TraceWriter(run_dir / "trace.jsonl") as writer:
        for i, case in enumerate(cases, start=1):
            started_at = datetime.now(UTC).isoformat()
            try:
                output = pipeline.answer(case.question)
                record = record_from_output(
                    output,
                    run_id=run_id,
                    case=case,
                    pipeline=pipeline,
                    dataset_id=dataset_path.stem,
                    corpus_manifest_sha=pipeline.corpus.manifest_sha,
                    started_at=started_at,
                )
                record.metrics = score_record(record, case, threshold, ks)
            except Exception as e:
                # Record and continue. See module docstring: excluding failures
                # is how a metric becomes an average over what happened to work.
                record = TraceRecord(
                    run_id=run_id,
                    case_id=case.id,
                    pipeline_name=cfg.name,
                    config_hash=cfg.config_hash,
                    pipeline_hash=cfg.pipeline_hash,
                    template_sha=pipeline.template_sha,
                    corpus_manifest_sha=pipeline.corpus.manifest_sha,
                    dataset_id=dataset_path.stem,
                    split=case.split.value,
                    query=case.question,
                    category=case.category,
                    answerable=case.answerable,
                    expected_behaviour=case.expected_abstention_behaviour.value,
                    started_at=started_at,
                    finished_at=datetime.now(UTC).isoformat(),
                    errors=[f"{type(e).__name__}: {e}"],
                )

            writer.write(record)
            records.append(record)
            status = "ERR " if record.errors else "ok  "
            print(
                f"  [{i:2d}/{len(cases)}] {status}{case.id:6s} {case.category:16s} "
                f"cache={'H' if record.cache_hit else 'M'} {record.latency_ms:7.0f}ms"
            )

    summary = summarise(records, cases, cfg)
    summary["run_id"] = run_id
    summary["wall_seconds"] = round(time.perf_counter() - started_wall, 2)
    summary["corpus_manifest_sha"] = pipeline.corpus.manifest_sha
    summary["n_chunks"] = len(pipeline.chunks)

    import json

    (run_dir / "metrics.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    return summary


def summarise(
    records: list[TraceRecord], cases: Sequence[EvalCase], config: PipelineConfig
) -> dict[str, Any]:
    """Aggregate, keeping deterministic and behavioural results separate."""
    ok = [r for r in records if not r.errors]
    by_case = {c.id: c for c in cases}

    def col(name: str) -> list[Any]:
        return [r.metrics.get(name) for r in ok]

    aggregate: dict[str, Any] = {
        "pipeline": config.name,
        "config_hash": config.config_hash,
        "pipeline_hash": config.pipeline_hash,
        "n_cases": len(records),
        "n_errors": len(records) - len(ok),
        "hit_coverage_threshold": config.evaluation.hit_coverage_threshold,
    }

    numeric = [
        *[f"recall_at_{k}" for k in config.evaluation.recall_at_k],
        *[f"precision_at_{k}" for k in config.evaluation.recall_at_k],
        *[f"ndcg_at_{k}" for k in config.evaluation.recall_at_k],
        "mrr",
        "document_recall",
        "required_fact_coverage",
        "citation_validity",
        "citation_precision_doc",
        "claim_citation_coverage",
    ]
    for name in numeric:
        values = col(name)
        mean = M.mean_ignoring_none(values)
        aggregate[name] = round(mean, 4) if mean is not None else None
        aggregate[f"{name}__n"] = len([v for v in values if v is not None])

    aggregate["abstention_accuracy"] = (
        round(sum(1 for r in ok if r.metrics.get("abstention_correct")) / len(ok), 4)
        if ok
        else None
    )
    aggregate["abstention_confusion"] = dict(
        Counter(
            f"{r.metrics.get('abstention_expected')}->{r.metrics.get('abstention_observed')}"
            for r in ok
        )
    )

    aggregate["total_fabricated_citations"] = sum(r.metrics.get("n_fabricated", 0) for r in ok)
    aggregate["total_non_authoritative_citations"] = sum(
        r.metrics.get("n_non_authoritative", 0) for r in ok
    )
    aggregate["total_forbidden_claims"] = sum(r.metrics.get("forbidden_claims", 0) for r in ok)

    latencies = sorted(r.latency_ms for r in ok)
    aggregate["latency"] = {
        "p50_ms": round(latencies[len(latencies) // 2], 1) if latencies else None,
        "p95_ms": round(latencies[int(len(latencies) * 0.95)], 1) if latencies else None,
        "mean_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        # Stated because it changes the meaning: with a warm cache the latency
        # figures measure the cache, not the pipeline.
        "cache_hit_rate": round(sum(1 for r in ok if r.cache_hit) / len(ok), 3) if ok else None,
        "note": "Cached calls replay stored latency. Read alongside cache_hit_rate.",
    }
    aggregate["tokens"] = {
        "prompt": sum(r.prompt_tokens for r in ok),
        "completion": sum(r.completion_tokens for r in ok),
        "total": sum(r.total_tokens for r in ok),
    }

    # Per-category, since a headline mean hides that all the loss is in one class.
    per_category: dict[str, Any] = {}
    for category in sorted({r.category for r in ok}):
        subset = [r for r in ok if r.category == category]
        per_category[category] = {
            "n": len(subset),
            "recall_at_4": M.mean_ignoring_none([r.metrics.get("recall_at_5") for r in subset]),
            "required_fact_coverage": M.mean_ignoring_none(
                [r.metrics.get("required_fact_coverage") for r in subset]
            ),
            "abstention_accuracy": sum(1 for r in subset if r.metrics.get("abstention_correct"))
            / len(subset),
        }
    aggregate["per_category"] = per_category
    aggregate["cases"] = {
        r.case_id: {
            "category": r.category,
            "errors": r.errors,
            **{k: v for k, v in r.metrics.items() if not isinstance(v, dict)},
        }
        for r in records
        if r.case_id in by_case
    }
    return aggregate
