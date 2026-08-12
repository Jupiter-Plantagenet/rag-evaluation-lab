"""The current development ablation uses only supported retrieval metrics."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from ablate_retrieval import METRIC_KEYS  # noqa: E402


@pytest.mark.unit
def test_current_ablation_metric_set_omits_deprecated_ndcg() -> None:
    assert METRIC_KEYS == [
        "recall_at_1",
        "recall_at_3",
        "recall_at_5",
        "recall_at_10",
        "mrr",
        "precision_at_4",
        "document_recall",
    ]


@pytest.mark.unit
def test_current_ablation_reports_omit_deprecated_ndcg() -> None:
    report_dir = ROOT / "reports" / "ablation"
    for name in (
        "dev-retrieval-ablation.md",
        "dev-retrieval-ablation.json",
        "dev-retrieval-ablation.csv",
    ):
        text = (report_dir / name).read_text(encoding="utf-8").lower()
        assert "ndcg" not in text
        assert "precision_at_4" in text
        assert "precision_at_5" not in text
