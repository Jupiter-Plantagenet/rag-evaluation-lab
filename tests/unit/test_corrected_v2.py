"""Invariants for the separate trace-derived corrected-v2 release."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag_eval.config import load_config
from rag_eval.reporting.compare import build_comparison
from rag_eval.reporting.corrected_v2 import sha256_file, write
from rag_eval.tracing.schema import read_traces

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "corrected-v2" / "held-out" / "comparison.json"
CSV_REPORT = ROOT / "reports" / "corrected-v2" / "held-out" / "comparison.csv"
MARKDOWN_REPORT = ROOT / "reports" / "corrected-v2" / "held-out" / "comparison.md"
BASE_TRACE = ROOT / "runs" / "baseline-test-20260806T182019Z-66ee099b" / "trace.jsonl"
IMPR_TRACE = ROOT / "runs" / "improved-test-20260806T182251Z-1e6a1bf8" / "trace.jsonl"


@pytest.mark.unit
def test_corrected_report_names_and_hashes_the_intended_frozen_sources() -> None:
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    source = payload["source"]
    assert source["baseline_run"] == "baseline-test-20260806T182019Z-66ee099b"
    assert source["improved_run"] == "improved-test-20260806T182251Z-1e6a1bf8"
    assert source["baseline_trace_sha256"] == sha256_file(BASE_TRACE)
    assert source["improved_trace_sha256"] == sha256_file(IMPR_TRACE)
    assert source["trace_only"] is True


@pytest.mark.unit
def test_common_budget_metrics_use_the_same_cutoff_for_both_arms() -> None:
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    configured = payload["configured_system_outcomes"]
    common = payload["common_budget_ranking_sensitivity"]
    assert (configured["baseline_budget"], configured["improved_budget"]) == (4, 8)
    assert common["budget"] == 4
    assert {row["metric"] for row in common["metrics"]} == {
        "recall",
        "mrr",
        "precision",
        "document_recall",
    }
    assert all(row["metric"] != "ndcg" for row in configured["metrics"])
    assert any("nDCG is retained only" in note for note in payload["deprecated_measurements"])
    assert "ndcg" not in CSV_REPORT.read_text(encoding="utf-8").lower()
    markdown = MARKDOWN_REPORT.read_text(encoding="utf-8")
    assert "nDCG is deprecated" in markdown
    assert "| nDCG" not in markdown
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "nDCG is deprecated" in readme
    assert "| nDCG" not in readme


@pytest.mark.unit
def test_historical_config_with_inert_judge_keys_still_loads() -> None:
    config = load_config(BASE_TRACE.parent / "config.resolved.yaml")
    assert config.name == "baseline"
    assert "judge_enabled" not in config.evaluation.model_dump()


@pytest.mark.unit
def test_historical_ndcg_fields_remain_readable_but_are_not_compared() -> None:
    historical = read_traces(BASE_TRACE)
    assert "ndcg_at_5" in historical[0]["metrics"]

    comparison = build_comparison(BASE_TRACE, IMPR_TRACE, resamples=100, seed=1)
    assert all("ndcg" not in metric.metric for metric in comparison.metrics)


@pytest.mark.unit
def test_corrected_v2_writes_canonical_lf_newlines(tmp_path: Path) -> None:
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    write(payload, tmp_path, "held-out")
    first = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    write(payload, tmp_path, "held-out")
    second = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    assert first == second
    assert all(b"\r\n" not in content for content in first.values())
