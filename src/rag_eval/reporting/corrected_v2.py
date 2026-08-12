"""Trace-only corrected metric reports (v2).

The original run directories and reports are evidence, not inputs to overwrite.
This module reads their JSONL records, recomputes only deterministic metrics,
and writes a separately-versioned derived report.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from rag_eval.evaluation import metrics as M  # noqa: N812
from rag_eval.reporting.compare import MetricComparison, compare_metric
from rag_eval.tracing.schema import read_traces
from rag_eval.types import EvalCase

METRICS = ("recall", "mrr", "precision", "document_recall")
METRIC_LABELS = {
    "recall": "span recall",
    "mrr": "MRR",
    "precision": "precision",
    "document_recall": "document recall",
}
METRIC_VERSION = "2.1.0"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_lf(path: Path, text: str) -> None:
    """Write a current derived report with canonical LF newlines."""
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _metrics_at_budget(
    record: dict[str, Any], case: EvalCase, budget: int, threshold: float
) -> dict[str, Any]:
    retrieved = [item for item in record["retrieved"] if int(item["rank"]) <= budget]
    return {
        "recall": M.recall_at_k(case, retrieved, budget, threshold),
        "mrr": M.mrr(case, retrieved, threshold),
        "precision": M.precision_at_k(case, retrieved, budget, threshold),
        "document_recall": M.document_recall(case, retrieved),
    }


def _scored_records(
    trace_path: Path, cases: dict[str, EvalCase], budget: int, threshold: float
) -> dict[str, dict[str, Any]]:
    return {
        record["case_id"]: {
            "metrics": _metrics_at_budget(record, cases[record["case_id"]], budget, threshold)
        }
        for record in read_traces(trace_path)
        if not record["errors"] and record["case_id"] in cases
    }


def _compare(
    baseline: dict[str, dict[str, Any]], improved: dict[str, dict[str, Any]], *, seed: int
) -> list[MetricComparison]:
    return [
        compare_metric(name, baseline, improved, resamples=10000, seed=seed) for name in METRICS
    ]


def _as_rows(comparisons: list[MetricComparison]) -> list[dict[str, Any]]:
    return [comparison.to_dict() for comparison in comparisons]


def derive(
    baseline_trace: Path,
    improved_trace: Path,
    cases: dict[str, EvalCase],
    *,
    threshold: float = 0.5,
    seed: int = 20260806,
) -> dict[str, Any]:
    """Return configured-system and common-budget comparisons from stored traces."""
    base_raw, impr_raw = read_traces(baseline_trace), read_traces(improved_trace)
    base_budget = min(int(record["top_k"]) for record in base_raw if not record["errors"])
    impr_budget = min(int(record["top_k"]) for record in impr_raw if not record["errors"])
    common_budget = min(base_budget, impr_budget)

    configured = _compare(
        _scored_records(baseline_trace, cases, base_budget, threshold),
        _scored_records(improved_trace, cases, impr_budget, threshold),
        seed=seed,
    )
    common = _compare(
        _scored_records(baseline_trace, cases, common_budget, threshold),
        _scored_records(improved_trace, cases, common_budget, threshold),
        seed=seed,
    )
    return {
        "metric_version": METRIC_VERSION,
        "metric_change": "nDCG is deprecated from v2 conclusions: the original definition double-counted overlapping chunks, while the bounded replacement incorrectly limited one retrieved chunk to one evidence unit.",
        "source": {
            "baseline_run": base_raw[0]["run_id"],
            "improved_run": impr_raw[0]["run_id"],
            "baseline_trace_sha256": sha256_file(baseline_trace),
            "improved_trace_sha256": sha256_file(improved_trace),
            "trace_only": True,
        },
        "configured_system_outcomes": {
            "baseline_budget": base_budget,
            "improved_budget": impr_budget,
            "estimand": "Outcomes of the complete configured pipelines at their actual retrieval budgets.",
            "metrics": _as_rows(configured),
        },
        "common_budget_ranking_sensitivity": {
            "budget": common_budget,
            "estimand": "Post-hoc sensitivity analysis with both arms capped at the same candidate budget.",
            "metrics": _as_rows(common),
        },
        "deprecated_measurements": [
            "nDCG is retained only in historical traces and reports. It is not a current v2 metric or conclusion.",
            "n_non_authoritative is retained only in historical traces and is excluded from v2 reporting; document-level ownership does not establish claim-specific, fact-specific, or time-specific source authority.",
        ],
    }


def render_markdown(payload: dict[str, Any], split: str) -> str:
    lines = [f"# Corrected derived metrics v2 — {split}", ""]
    source = payload["source"]
    lines += [
        "This is a trace-only re-score. The original traces and frozen reports remain unchanged.",
        "",
        f"- source runs: `{source['baseline_run']}` / `{source['improved_run']}`",
        f"- source trace SHA-256: `{source['baseline_trace_sha256']}` / `{source['improved_trace_sha256']}`",
        f"- corrected metric version: `{payload['metric_version']}`",
        f"- metric change: {payload['metric_change']}",
        "- current retrieval metrics: evidence-span recall, MRR, precision, and document recall.",
        "- citation authority: the historical document-level flag is deprecated trace metadata and is not a citation-quality conclusion.",
        "",
    ]
    for section, title in (
        ("configured_system_outcomes", "Configured-system outcomes"),
        ("common_budget_ranking_sensitivity", "Common-budget ranking sensitivity (post-hoc)"),
    ):
        item = payload[section]
        lines += [f"## {title}", "", item["estimand"], ""]
        if section == "configured_system_outcomes":
            lines += [
                f"Baseline: k={item['baseline_budget']}; improved: k={item['improved_budget']}.",
                "",
            ]
        else:
            lines += [f"Both arms capped at k={item['budget']}.", ""]
        lines += [
            "| Metric | n | Baseline | Improved | Delta | 95% CI |",
            "|---|---:|---:|---:|---:|:---:|",
        ]
        for row in item["metrics"]:
            ci = (
                f"[{row['ci_low']:+.3f}, {row['ci_high']:+.3f}]"
                if row["ci_low"] is not None
                else "-"
            )
            lines.append(
                f"| {METRIC_LABELS[row['metric']]} | {row['n_paired']} | {row['baseline']:.3f} | {row['improved']:.3f} | {row['delta']:+.3f} | {ci} |"
            )
        lines.append("")
    return "\n".join(lines)


def write(payload: dict[str, Any], out_dir: Path, split: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_lf(
        out_dir / "comparison.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )
    _write_lf(out_dir / "comparison.md", render_markdown(payload, split))
    rows = []
    for analysis, section in (
        ("configured_system_outcomes", "configured_system_outcomes"),
        ("common_budget_ranking_sensitivity", "common_budget_ranking_sensitivity"),
    ):
        for row in payload[section]["metrics"]:
            rows.append({"analysis": analysis, **row})
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(
        handle,
        fieldnames=(
            "analysis",
            "metric",
            "n_paired",
            "baseline",
            "improved",
            "delta",
            "ci_low",
            "ci_high",
            "ci_excludes_zero",
            "direction",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    _write_lf(out_dir / "comparison.csv", handle.getvalue())
