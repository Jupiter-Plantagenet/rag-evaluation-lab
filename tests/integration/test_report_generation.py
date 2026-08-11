"""Two fixture runs, compared, rendered into the three report artefacts.

The comparison code is unit-tested against synthetic per-case dictionaries. That
proves the statistics; it does not prove the statistics can read a trace this
project actually wrote. This test closes that gap by generating real traces from
the real pipeline and feeding them to `build_comparison` unchanged.

It also pins the property the reporting design turns on: JSON, Markdown and CSV
are rendered from ONE `Comparison` object, so the three cannot disagree.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from rag_eval.reporting.compare import build_comparison, render_csv, render_markdown, write_all
from rag_eval.runner import score_record
from rag_eval.tracing.schema import TraceWriter, record_from_output
from rag_eval.types import EvalCase

pytestmark = pytest.mark.integration


def _write_run(
    build_fixture_pipeline: Any,
    cases: list[EvalCase],
    path: Path,
    run_id: str,
    **overrides: Any,
) -> Path:
    pipeline, generator = build_fixture_pipeline(**overrides)
    with TraceWriter(path) as writer:
        for case in cases:
            generator.case_id = case.id
            output = pipeline.answer(case.question)
            record = record_from_output(
                output,
                run_id=run_id,
                case=case,
                pipeline=pipeline,
                dataset_id="fixture_v1",
                corpus_manifest_sha=pipeline.corpus.manifest_sha,
                started_at=datetime.now(UTC).isoformat(),
            )
            record.metrics = score_record(record, case, 0.5, [1, 3, 5, 10])
            writer.write(record)
    return path


@pytest.fixture
def two_runs(build_fixture_pipeline: Any, fixture_cases: Any, tmp_path: Path) -> tuple[Path, Path]:
    cases = list(fixture_cases)
    base = _write_run(
        build_fixture_pipeline,
        cases,
        tmp_path / "base.jsonl",
        "fixture-base",
        retrieval={"kind": "dense", "top_k": 2},
    )
    impr = _write_run(
        build_fixture_pipeline,
        cases,
        tmp_path / "impr.jsonl",
        "fixture-impr",
        retrieval={"kind": "hybrid_rrf", "top_k": 4},
    )
    return base, impr


def test_comparison_reads_real_traces_and_pairs_them_by_case(two_runs: tuple[Path, Path]) -> None:
    base, impr = two_runs
    comparison = build_comparison(base, impr, resamples=300, seed=1)

    assert comparison.n_cases == 4
    assert comparison.baseline_run == "fixture-base"
    assert comparison.improved_run == "fixture-impr"

    for metric in comparison.metrics:
        assert metric.n_paired <= comparison.n_cases
        if metric.ci_low is not None:
            assert metric.ci_low <= metric.ci_high
            assert metric.ci_excludes_zero == (not (metric.ci_low <= 0.0 <= metric.ci_high))

    # FX-03 is unanswerable: it must be absent from every retrieval denominator.
    by_name = {m.metric: m for m in comparison.metrics}
    if "recall_at_3" in by_name:
        assert by_name["recall_at_3"].n_paired <= 3


def test_abstention_is_reported_with_a_paired_interval(two_runs: tuple[Path, Path]) -> None:
    base, impr = two_runs
    c = build_comparison(base, impr, resamples=300, seed=1)

    assert c.abstention["n"] == 4
    for key in ("baseline_accuracy", "improved_accuracy", "delta", "ci_low", "ci_high"):
        assert key in c.abstention
    assert c.abstention["ci_low"] <= c.abstention["ci_high"]
    assert c.abstention["ci_excludes_zero"] == (
        not (c.abstention["ci_low"] <= 0.0 <= c.abstention["ci_high"])
    )


def test_per_category_denominators_are_paired(two_runs: tuple[Path, Path]) -> None:
    """Audit finding A-4: a row's two means must describe the same case set."""
    base, impr = two_runs
    c = build_comparison(base, impr, resamples=300, seed=1)

    for name, row in c.per_category.items():
        assert row["n_recall_at_5"] <= row["n"], name
        assert row["n_fact_coverage"] <= row["n"], name
        if row["baseline_recall_at_5"] is None:
            assert row["improved_recall_at_5"] is None, (
                f"{name}: one arm has a mean and the other does not, so the row "
                "compares different case sets"
            )
        if row["baseline_fact_coverage"] is None:
            assert row["improved_fact_coverage"] is None, name


def test_the_three_artefacts_are_written_and_cannot_disagree(
    two_runs: tuple[Path, Path], tmp_path: Path
) -> None:
    base, impr = two_runs
    comparison = build_comparison(base, impr, resamples=300, seed=1)
    out = tmp_path / "reports"
    paths = write_all(comparison, out)

    assert set(paths) == {"json", "markdown", "csv"}
    for path in paths.values():
        assert path.exists() and path.stat().st_size > 0

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    rows = list(csv.DictReader(paths["csv"].read_text(encoding="utf-8").splitlines()))
    markdown = paths["markdown"].read_text(encoding="utf-8")

    assert len(rows) == len(payload["metrics"])
    for row, metric in zip(rows, payload["metrics"], strict=True):
        assert row["metric"] == metric["metric"]
        assert int(row["n_paired"]) == metric["n_paired"]
        assert float(row["delta"]) == pytest.approx(metric["delta"])
        assert (row["ci_excludes_zero"] == "True") == metric["ci_excludes_zero"]
        assert metric["metric"] in markdown


def test_reports_use_the_precise_field_name_not_significant(
    two_runs: tuple[Path, Path], tmp_path: Path
) -> None:
    """`significant` claimed a hypothesis test this procedure never performs."""
    base, impr = two_runs
    comparison = build_comparison(base, impr, resamples=300, seed=1)

    csv_text = render_csv(comparison)
    json_text = json.dumps(comparison.to_dict())
    markdown = render_markdown(comparison)

    assert "ci_excludes_zero" in csv_text
    assert "significant" not in csv_text
    assert "significant" not in json_text
    assert "significant" not in markdown.lower(), (
        "public-facing prose must not use the vocabulary of significance testing"
    )
    assert "paired bootstrap" in markdown.lower()


def test_report_is_deterministic_under_a_fixed_seed(two_runs: tuple[Path, Path]) -> None:
    base, impr = two_runs
    first = render_markdown(build_comparison(base, impr, resamples=500, seed=99))
    second = render_markdown(build_comparison(base, impr, resamples=500, seed=99))
    assert first == second
