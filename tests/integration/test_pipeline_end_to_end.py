"""The whole pipeline over the fixture corpus, offline, with a frozen answer.

This is the test the CI stage exists for. Every unit test in this repository can
pass while the assembled system is broken -- a chunker that drops offsets, a
retriever that returns chunks the context packer mislabels, a binder that
resolves against a different retrieval pass than the one the model saw. Those are
integration failures by construction, and the predecessor project shipped exactly
that class of defect with a green-looking test suite.

Route under test:

    fixture corpus -> chunking -> retrieval -> context labels -> frozen answer
      -> claim splitting -> citation binding -> trace record -> metrics
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from rag_eval.evaluation import metrics as M  # noqa: N812 - matches the runner's convention
from rag_eval.runner import score_record, summarise
from rag_eval.tracing.schema import TraceWriter, read_traces, record_from_output
from rag_eval.types import EvalCase

pytestmark = pytest.mark.integration


def _run_case(pipeline: Any, generator: Any, case: EvalCase) -> Any:
    generator.case_id = case.id
    return pipeline.answer(case.question)


# ---------------------------------------------------------------------------
# The complete route
# ---------------------------------------------------------------------------


def test_complete_offline_pipeline_from_corpus_to_metrics(
    build_fixture_pipeline: Any, fixture_case_map: dict[str, EvalCase], tmp_path: Path
) -> None:
    """One case, every stage, ending in a scored trace record on disk."""
    pipeline, generator = build_fixture_pipeline()
    case = fixture_case_map["FX-01"]
    started = datetime.now(UTC).isoformat()

    output = _run_case(pipeline, generator, case)

    # --- retrieval -------------------------------------------------------
    assert len(output.retrieved) == 3, "top_k must be honoured"
    assert [sc.rank for sc in output.retrieved] == [1, 2, 3], "ranks must be 1-based and dense"
    assert any(sc.chunk.doc_id == "widget-pricing" for sc in output.retrieved)

    # --- context labels --------------------------------------------------
    assert set(output.context_labels) == {"C1", "C2", "C3"}
    retrieved_ids = {sc.chunk.chunk_id for sc in output.retrieved}
    assert set(output.context_labels.values()) == retrieved_ids, (
        "every label must point at a chunk that was actually retrieved -- this is "
        "the property whose absence made the predecessor's citations meaningless"
    )
    for label, chunk_id in output.context_labels.items():
        assert f"[{label}]" in output.context_text
        assert chunk_id in retrieved_ids

    # --- generation and claims -------------------------------------------
    assert "47 credits" in output.answer
    assert len(output.claims) >= 1
    assert output.claims[0].cited_labels == ("C1",)

    # --- citation binding ------------------------------------------------
    assert len(output.citations) == 1
    citation = output.citations[0]
    assert citation.resolved is True
    assert citation.chunk_id == output.context_labels["C1"]
    assert citation.doc_id is not None
    assert citation.source_char_start is not None and citation.source_char_end is not None
    assert citation.source_char_end > citation.source_char_start
    assert output.unresolved_labels == ()

    # The quoted text must be the real source bytes, not the chunk's own copy.
    body = pipeline.corpus.bodies()[citation.doc_id]
    assert citation.quoted_text
    assert citation.quoted_text[:80] in body[citation.source_char_start : citation.source_char_end]

    # --- trace record ----------------------------------------------------
    record = record_from_output(
        output,
        run_id="itest-0001",
        case=case,
        pipeline=pipeline,
        dataset_id="fixture_v1",
        corpus_manifest_sha=pipeline.corpus.manifest_sha,
        started_at=started,
    )
    record.metrics = score_record(record, case, 0.5, [1, 3, 5, 10])
    assert not any(name.startswith("ndcg_at_") for name in record.metrics)

    trace_path = tmp_path / "trace.jsonl"
    with TraceWriter(trace_path) as writer:
        writer.write(record)

    # --- round-trip ------------------------------------------------------
    (reloaded,) = read_traces(trace_path)
    assert reloaded["case_id"] == "FX-01"
    assert reloaded["schema_version"] == record.schema_version
    assert reloaded["context_labels"] == output.context_labels
    assert reloaded["metrics"]["recall_at_3"] is not None
    assert reloaded["metrics"]["citation_validity"] == 1.0
    assert reloaded["metrics"]["n_fabricated"] == 0
    assert reloaded["metrics"]["required_fact_coverage"] == 1.0
    assert reloaded["metrics"]["abstention_correct"] is True
    assert not any(name.startswith("ndcg_at_") for name in reloaded["metrics"])

    summary = summarise([record], [case], pipeline.config)
    assert not any(name.startswith("ndcg_at_") for name in summary)
    assert not any(name.startswith("ndcg_at_") for name in summary["cases"][case.id])

    # JSON, not repr: the trace is a data contract other tools read.
    assert json.loads(trace_path.read_text(encoding="utf-8").strip())["run_id"] == "itest-0001"


# ---------------------------------------------------------------------------
# Stages that fail independently
# ---------------------------------------------------------------------------


def test_corpus_loads_with_offsets_that_index_the_real_body(fixture_corpus: Any) -> None:
    assert set(fixture_corpus.documents) == {
        "widget-pricing",
        "widget-pricing-legacy",
        "shipping-policy",
    }
    assert fixture_corpus["widget-pricing-legacy"].is_superseded is True
    assert fixture_corpus["widget-pricing"].is_superseded is False
    assert "fixture.widget.unit_price" in fixture_corpus["widget-pricing"].authoritative_for
    assert len(fixture_corpus.manifest_sha) == 64


def test_chunking_preserves_character_offsets_into_the_document(
    build_fixture_pipeline: Any,
) -> None:
    """A chunk whose offsets do not index its own text cannot ground a citation."""
    pipeline, _ = build_fixture_pipeline()
    bodies = pipeline.corpus.bodies()
    assert pipeline.chunks, "chunking produced nothing"
    for chunk in pipeline.chunks:
        body = bodies[chunk.doc_id]
        assert 0 <= chunk.char_start < chunk.char_end <= len(body)
        assert chunk.text.strip() in body[chunk.char_start : chunk.char_end]


def test_evidence_span_is_retrievable_for_every_answerable_fixture_case(
    build_fixture_pipeline: Any, fixture_cases: Any
) -> None:
    """The fixture set must be solvable, or its failures mean nothing."""
    pipeline, generator = build_fixture_pipeline(retrieval={"top_k": 5})
    for case in fixture_cases:
        if not case.expected_evidence_spans:
            continue
        output = _run_case(pipeline, generator, case)
        retrieved = [
            {
                "rank": sc.rank,
                "doc_id": sc.chunk.doc_id,
                "char_start": sc.chunk.char_start,
                "char_end": sc.chunk.char_end,
            }
            for sc in output.retrieved
        ]
        recall = M.recall_at_k(case, retrieved, 5, 0.5)
        assert recall is not None and recall > 0.0, f"{case.id}: no expected span retrieved at k=5"


def test_unanswerable_case_leaves_retrieval_metrics_undefined_not_zero(
    build_fixture_pipeline: Any, fixture_case_map: dict[str, EvalCase]
) -> None:
    """None means 'not applicable'. Zero would blame retrieval for a gap."""
    pipeline, generator = build_fixture_pipeline()
    case = fixture_case_map["FX-03"]
    output = _run_case(pipeline, generator, case)

    record = record_from_output(
        output,
        run_id="itest-0002",
        case=case,
        pipeline=pipeline,
        dataset_id="fixture_v1",
        corpus_manifest_sha=pipeline.corpus.manifest_sha,
        started_at=datetime.now(UTC).isoformat(),
    )
    record.metrics = score_record(record, case, 0.5, [1, 3, 5, 10])

    assert record.metrics["recall_at_3"] is None
    assert record.metrics["document_recall"] is None
    assert record.metrics["required_fact_coverage"] is None
    assert record.abstained is True
    assert record.metrics["abstention_correct"] is True


def test_a_label_the_model_invents_is_counted_not_dropped(
    build_fixture_pipeline: Any, fixture_case_map: dict[str, EvalCase]
) -> None:
    """FX-02 cites [C9] with only three chunks in context.

    Dropping it would report zero fabricated citations, which is the failure this
    whole citation design exists to make visible.
    """
    pipeline, generator = build_fixture_pipeline()
    case = fixture_case_map["FX-02"]
    output = _run_case(pipeline, generator, case)

    assert "C9" in output.unresolved_labels
    fabricated = [c for c in output.citations if not c.resolved]
    assert len(fabricated) == 1
    assert fabricated[0].label == "C9"
    assert fabricated[0].chunk_id is None

    stats = M.citation_metrics(
        case,
        [
            {
                "resolved": c.resolved,
                "doc_id": c.doc_id,
                "claim_id": c.claim_id,
                "authoritative": c.authoritative,
            }
            for c in output.citations
        ],
        [{"claim_id": c.claim_id, "text": c.text} for c in output.claims],
    )
    assert stats["n_fabricated"] == 1
    assert stats["citation_validity"] is not None and stats["citation_validity"] < 1.0


def test_retrieval_kinds_all_assemble_and_return_ranked_results(
    build_fixture_pipeline: Any,
) -> None:
    """dense, bm25 and hybrid_rrf must each build from config alone."""
    for kind in ("dense", "bm25", "hybrid_rrf"):
        pipeline, generator = build_fixture_pipeline(retrieval={"kind": kind, "top_k": 3})
        generator.case_id = "FX-01"
        output = pipeline.answer("What is the standard widget unit price?")
        assert [sc.rank for sc in output.retrieved] == [1, 2, 3], f"{kind} produced bad ranks"
        assert len({sc.chunk.chunk_id for sc in output.retrieved}) == 3, f"{kind} returned a dup"


def test_the_two_pipelines_differ_only_by_configuration(build_fixture_pipeline: Any) -> None:
    """Config, not code, is the experimental manipulation.

    Two configs that differ only in retrieval settings must produce different
    pipeline hashes; two that differ only by label must not.
    """
    baselineish, _ = build_fixture_pipeline(retrieval={"kind": "dense", "top_k": 3})
    improvedish, _ = build_fixture_pipeline(retrieval={"kind": "hybrid_rrf", "top_k": 6})
    renamed, _ = build_fixture_pipeline(
        name="different-label", retrieval={"kind": "dense", "top_k": 3}
    )

    assert baselineish.config.pipeline_hash != improvedish.config.pipeline_hash
    assert baselineish.config.pipeline_hash == renamed.config.pipeline_hash, (
        "renaming a run must not make it look like a different experiment"
    )
    assert baselineish.config.config_hash != renamed.config.config_hash, (
        "config_hash covers the whole config, including the label"
    )
