"""Dev-only retrieval ablation.

The improved arm changes four things at once -- structure-aware chunking, hybrid
dense+BM25 fusion, top_k 4 -> 8, and near-duplicate removal. That supports a
package-level comparison and supports no statement whatever about which component
did the work. This script separates them.

It is EXPLANATORY ONLY. Three constraints follow from that and are enforced or
stated throughout:

1. **Dev split only.** `load_cases(split=DEV)` is the only path used, so no
   ledger entry is written and the held-out split is untouched.
2. **No new production configuration may be selected from these numbers.** The
   improved arm is frozen. If a variant here looks better than F, that is a
   finding about attribution, not a licence to reconfigure.
3. **Descriptive, not a factorial causal study.** Six of the sixteen cells of a
   2x2x2x2 design are run. The components interact -- near-duplicate removal only
   does anything at a k large enough to admit duplicates, and hybrid fusion
   changes which chunks exist to be deduplicated -- so differences between rows
   are not clean main effects.

No generation calls are made. Retrieval metrics are a pure function of the
retrieved list and the ground-truth spans, so this needs no model, no key, and no
cache beyond embeddings.

Usage:
    python scripts/ablate_retrieval.py [--out reports/ablation] [--embedder minilm]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from rag_eval.data.loader import load_cases  # noqa: E402
from rag_eval.evaluation import metrics as M  # noqa: E402,N812
from rag_eval.ingest.chunkers import build_chunker  # noqa: E402
from rag_eval.ingest.corpus import load_corpus  # noqa: E402
from rag_eval.retrieval.embedders import build_embedder  # noqa: E402
from rag_eval.retrieval.retrievers import (  # noqa: E402
    BM25Retriever,
    DenseRetriever,
    ReciprocalRankFusionRetriever,
    deduplicate_by_overlap,
)
from rag_eval.types import EvalCase, Split  # noqa: E402

HIT_THRESHOLD = 0.5

FIXED = ("fixed_size", {"chunk_size": 500, "chunk_overlap": 50})
STRUCTURE = (
    "markdown_structure",
    {"chunk_size": 500, "chunk_overlap": 50, "max_chars": 1200, "min_chars": 120},
)


@dataclass(frozen=True)
class Variant:
    key: str
    label: str
    chunker: tuple[str, dict[str, Any]]
    retrieval: str
    top_k: int
    deduplicate: bool
    note: str


# Exactly the six configurations named in the Phase-4 brief. A and F are the two
# frozen arms' retrieval halves; B-E isolate one component at a time.
VARIANTS = [
    Variant("A", "baseline", FIXED, "dense", 4, False, "the frozen baseline arm's retrieval"),
    Variant("B", "structure-only", STRUCTURE, "dense", 4, False, "intervention 1 alone"),
    Variant("C", "hybrid-only", FIXED, "hybrid_rrf", 4, False, "intervention 2 alone"),
    Variant("D", "budget-only", FIXED, "dense", 8, False, "intervention 3 alone"),
    Variant("E", "structure+hybrid", STRUCTURE, "hybrid_rrf", 4, False, "interventions 1+2"),
    Variant("F", "full improved", STRUCTURE, "hybrid_rrf", 8, True, "the frozen improved arm"),
]

METRIC_KEYS = [
    "recall_at_1",
    "recall_at_3",
    "recall_at_5",
    "recall_at_10",
    "mrr",
    "precision_at_5",
    "ndcg_at_5",
    "document_recall",
]


@dataclass
class VariantResult:
    variant: Variant
    n_chunks: int
    per_case: dict[str, dict[str, float | None]] = field(default_factory=dict)
    means: dict[str, float | None] = field(default_factory=dict)
    latency_ms: dict[str, float] = field(default_factory=dict)


def build_retriever(variant: Variant, chunks: list[Any], embedder_kind: str) -> Any:
    embedder = build_embedder(embedder_kind)
    if hasattr(embedder, "fit"):
        embedder.fit([c.text for c in chunks])
    matrix = embedder.encode([c.text for c in chunks])
    dense = DenseRetriever(chunks, matrix, embedder)
    if variant.retrieval == "dense":
        return dense
    return ReciprocalRankFusionRetriever([dense, BM25Retriever(chunks)], k_rrf=60, fetch_k=30)


def run_variant(variant: Variant, cases: list[EvalCase], embedder_kind: str) -> VariantResult:
    corpus = load_corpus(REPO_ROOT / "data" / "corpus" / "novapay")
    kind, params = variant.chunker
    chunker = build_chunker(kind, **params)
    chunks = [c for doc in corpus.documents.values() for c in chunker.chunk(doc)]

    retriever = build_retriever(variant, chunks, embedder_kind)
    result = VariantResult(variant=variant, n_chunks=len(chunks))
    latencies: list[float] = []

    for case in cases:
        started = time.perf_counter()
        scored = retriever.retrieve(case.question, variant.top_k)
        if variant.deduplicate:
            scored = deduplicate_by_overlap(scored, 0.8)
        latencies.append((time.perf_counter() - started) * 1000.0)

        retrieved = [
            {
                "rank": sc.rank,
                "chunk_id": sc.chunk.chunk_id,
                "doc_id": sc.chunk.doc_id,
                "char_start": sc.chunk.char_start,
                "char_end": sc.chunk.char_end,
            }
            for sc in scored
        ]
        result.per_case[case.id] = {
            "recall_at_1": M.recall_at_k(case, retrieved, 1, HIT_THRESHOLD),
            "recall_at_3": M.recall_at_k(case, retrieved, 3, HIT_THRESHOLD),
            "recall_at_5": M.recall_at_k(case, retrieved, 5, HIT_THRESHOLD),
            "recall_at_10": M.recall_at_k(case, retrieved, 10, HIT_THRESHOLD),
            "mrr": M.mrr(case, retrieved, HIT_THRESHOLD),
            "precision_at_5": M.precision_at_k(case, retrieved, 5, HIT_THRESHOLD),
            "ndcg_at_5": M.ndcg_at_k(case, retrieved, 5, HIT_THRESHOLD),
            "document_recall": M.document_recall(case, retrieved),
        }

    for key in METRIC_KEYS:
        result.means[key] = M.mean_ignoring_none(
            [result.per_case[c.id][key] for c in cases]  # type: ignore[misc]
        )

    result.latency_ms = {
        "mean": round(statistics.fmean(latencies), 2),
        "p50": round(statistics.median(latencies), 2),
        "max": round(max(latencies), 2),
    }
    return result


def render_markdown(results: list[VariantResult], embedder_kind: str, n_cases: int) -> str:
    lines: list[str] = []
    a = lines.append

    a("# Dev-only retrieval ablation")
    a("")
    a(f"- split: **dev** (n={n_cases}). The held-out split is not read by this analysis.")
    a(f"- embedder: `{embedder_kind}` (as used by both frozen arms)")
    a(f"- hit coverage threshold: {HIT_THRESHOLD}")
    a("- no generation calls; retrieval metrics are a pure function of the retrieved list")
    a("")
    a("> **Explanatory only.** These numbers exist to attribute the package-level")
    a("> difference to components. They do **not** select a new configuration: the")
    a("> improved arm is frozen, and no variant below may be promoted on the strength")
    a("> of this table.")
    a("")
    a("> **Descriptive, not a factorial causal study.** Six of the sixteen cells of a")
    a("> 2x2x2x2 design are run, and the components interact -- near-duplicate removal")
    a("> does nothing at a k too small to admit duplicates, and hybrid fusion changes")
    a("> which chunks exist to be deduplicated. Differences between rows are therefore")
    a("> not clean main effects, and no confidence intervals are given: these are")
    a("> single deterministic runs over one 28-case split, not repeated measurements.")
    a("")

    a("## Configurations")
    a("")
    a("| | Variant | Chunker | Retrieval | top_k | Dedupe | Chunks | Note |")
    a("|---|---|---|---|---:|---|---:|---|")
    for r in results:
        v = r.variant
        a(
            f"| {v.key} | {v.label} | {v.chunker[0]} | {v.retrieval} | {v.top_k} "
            f"| {'yes' if v.deduplicate else 'no'} | {r.n_chunks} | {v.note} |"
        )
    a("")

    a("## Retrieval metrics")
    a("")
    header = "| | Variant | " + " | ".join(METRIC_KEYS) + " | mean ms |"
    a(header)
    a("|---|---|" + "---:|" * (len(METRIC_KEYS) + 1))
    for r in results:
        cells = []
        for key in METRIC_KEYS:
            value = r.means[key]
            cells.append(f"{value:.3f}" if value is not None else "-")
        a(
            f"| {r.variant.key} | {r.variant.label} | "
            + " | ".join(cells)
            + f" | {r.latency_ms['mean']} |"
        )
    a("")

    base = results[0]
    a("## Change from A (baseline)")
    a("")
    a("| | Variant | " + " | ".join(METRIC_KEYS) + " |")
    a("|---|---|" + "---:|" * len(METRIC_KEYS))
    for r in results[1:]:
        cells = []
        for key in METRIC_KEYS:
            value, ref = r.means[key], base.means[key]
            cells.append(f"{value - ref:+.3f}" if value is not None and ref is not None else "-")
        a(f"| {r.variant.key} | {r.variant.label} | " + " | ".join(cells) + " |")
    a("")

    a("## Reading `recall_at_10`")
    a("")
    a("`recall_at_k` filters the retrieved list by `rank <= k`, so a cutoff above a")
    a("variant's `top_k` degrades to 'everything this variant retrieved'. For the k=4")
    a("variants (A, B, C, E) recall@5 and recall@10 are both recall@4. Compare rows at")
    a("a cutoff no larger than the smallest `top_k` involved -- recall@1 and recall@3")
    a("are the only columns comparable across every row. This is audit finding A-13.")
    a("")

    # --- the comparison that is actually valid across rows -------------------
    matched = [r for r in results if r.variant.top_k == 4]
    a("## Attribution at a matched budget (k=4 only)")
    a("")
    a("A, B, C and E all retrieve four chunks, so every column below is a like-for-like")
    a("comparison and any difference is attributable to chunking or fusion rather than")
    a("to how much context the variant was allowed.")
    a("")
    matched_keys = ["recall_at_1", "recall_at_3", "mrr", "ndcg_at_5", "precision_at_5"]
    a("| | Variant | " + " | ".join(matched_keys) + " |")
    a("|---|---|" + "---:|" * len(matched_keys))
    for r in matched:
        cells = [f"{r.means[k]:.3f}" if r.means[k] is not None else "-" for k in matched_keys]
        a(f"| {r.variant.key} | {r.variant.label} | " + " | ".join(cells) + " |")
    a("")

    a("## The budget component, isolated")
    a("")
    a("Two pairs differ only by `top_k` (and, for E->F, the near-duplicate removal that")
    a("only becomes active at the larger k).")
    a("")
    budget_keys = [
        "recall_at_1",
        "recall_at_3",
        "recall_at_10",
        "mrr",
        "precision_at_5",
        "document_recall",
    ]
    by_key = {r.variant.key: r for r in results}
    a("| Pair | Change | " + " | ".join(budget_keys) + " |")
    a("|---|---|" + "---:|" * len(budget_keys))
    for left, right, label in (("A", "D", "k 4->8, fixed+dense"), ("E", "F", "k 4->8 + dedupe")):
        cells = []
        for key in budget_keys:
            lo, hi = by_key[left].means[key], by_key[right].means[key]
            cells.append(f"{hi - lo:+.3f}" if lo is not None and hi is not None else "-")
        a(f"| {left} -> {right} | {label} | " + " | ".join(cells) + " |")
    a("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(REPO_ROOT / "reports" / "ablation"))
    parser.add_argument("--embedder", default="minilm")
    args = parser.parse_args()

    corpus = load_corpus(REPO_ROOT / "data" / "corpus" / "novapay")
    cases = list(
        load_cases(
            REPO_ROOT / "data" / "eval" / "novapay_v1.yaml",
            split=Split.DEV,
            corpus=corpus.bodies(),
            repo_root=REPO_ROOT,
        )
    )

    results = []
    for variant in VARIANTS:
        print(f"  {variant.key} {variant.label:18s} ...", end="", flush=True)
        result = run_variant(variant, cases, args.embedder)
        results.append(result)
        recall3 = result.means["recall_at_3"]
        print(f" {result.n_chunks:4d} chunks, recall@3 {recall3:.3f}" if recall3 else " done")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "dev-retrieval-ablation.md").write_text(
        render_markdown(results, args.embedder, len(cases)), encoding="utf-8"
    )
    (out_dir / "dev-retrieval-ablation.json").write_text(
        json.dumps(
            {
                "split": "dev",
                "n_cases": len(cases),
                "embedder": args.embedder,
                "hit_coverage_threshold": HIT_THRESHOLD,
                "explanatory_only": True,
                "variants": [
                    {
                        "key": r.variant.key,
                        "label": r.variant.label,
                        "chunker": r.variant.chunker[0],
                        "chunker_params": r.variant.chunker[1],
                        "retrieval": r.variant.retrieval,
                        "top_k": r.variant.top_k,
                        "deduplicate": r.variant.deduplicate,
                        "n_chunks": r.n_chunks,
                        "means": r.means,
                        "latency_ms": r.latency_ms,
                        "per_case": r.per_case,
                    }
                    for r in results
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    rows = ["variant,label," + ",".join(METRIC_KEYS) + ",mean_latency_ms,n_chunks"]
    for r in results:
        values = ",".join(
            f"{r.means[k]:.4f}" if r.means[k] is not None else "" for k in METRIC_KEYS
        )
        rows.append(
            f"{r.variant.key},{r.variant.label},{values},{r.latency_ms['mean']},{r.n_chunks}"
        )
    (out_dir / "dev-retrieval-ablation.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    print(f"\nwrote three artefacts to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
