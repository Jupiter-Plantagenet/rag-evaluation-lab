"""Baseline-vs-improved comparison with paired bootstrap confidence intervals.

The intervals are the point. Two means differing by 0.11 on 22 cases is not a
result; it is an observation that may or may not survive resampling. Reporting
the delta without an interval invites the reader to treat noise as an effect,
which at this sample size is the likeliest way for this project to mislead.

**Paired**, not independent: both pipelines answer the SAME cases, so the
per-case difference is the unit of analysis. Treating the arms as independent
samples would discard that pairing and produce intervals substantially wider
than the design warrants -- understating a real effect rather than overstating
it, but wrong either way.

Any interval containing zero is reported as **"no measurable difference"**, not
as an improvement with a caveat attached.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from rag_eval.tracing.schema import read_traces


@dataclass
class MetricComparison:
    metric: str
    n_paired: int
    baseline_mean: float | None
    improved_mean: float | None
    delta: float | None
    ci_low: float | None
    ci_high: float | None
    significant: bool
    direction: str  # "improved" | "regressed" | "no measurable difference"

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "n_paired": self.n_paired,
            "baseline": self.baseline_mean,
            "improved": self.improved_mean,
            "delta": self.delta,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "significant": self.significant,
            "direction": self.direction,
        }


def paired_bootstrap(
    baseline: list[float],
    improved: list[float],
    *,
    resamples: int = 10000,
    seed: int = 20260806,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Return (mean delta, ci_low, ci_high) for improved minus baseline.

    Resamples CASES, carrying both arms' values together, which is what makes
    the interval paired.
    """
    diffs = np.asarray(improved, dtype=float) - np.asarray(baseline, dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.choice(diffs, size=(resamples, len(diffs)), replace=True).mean(axis=1)
    return (
        float(diffs.mean()),
        float(np.percentile(draws, 100 * alpha / 2)),
        float(np.percentile(draws, 100 * (1 - alpha / 2))),
    )


def compare_metric(
    metric: str,
    base_by_case: dict[str, dict],
    impr_by_case: dict[str, dict],
    *,
    resamples: int,
    seed: int,
) -> MetricComparison:
    """Compare one metric over cases where BOTH arms defined it.

    Restricting to cases defined in both is what keeps the pairing honest. If
    one arm scored a case and the other returned None, including it would
    compare different case sets under one label.
    """
    pairs = [
        (base_by_case[cid]["metrics"].get(metric), impr_by_case[cid]["metrics"].get(metric))
        for cid in sorted(set(base_by_case) & set(impr_by_case))
    ]
    usable = [
        (b, i) for b, i in pairs if isinstance(b, (int, float)) and isinstance(i, (int, float))
    ]
    if len(usable) < 3:
        return MetricComparison(metric, len(usable), None, None, None, None, None, False, "insufficient data")

    base = [float(b) for b, _ in usable]
    impr = [float(i) for _, i in usable]
    delta, lo, hi = paired_bootstrap(base, impr, resamples=resamples, seed=seed)

    significant = not (lo <= 0.0 <= hi)
    if not significant:
        direction = "no measurable difference"
    else:
        direction = "improved" if delta > 0 else "regressed"

    return MetricComparison(
        metric=metric,
        n_paired=len(usable),
        baseline_mean=round(sum(base) / len(base), 4),
        improved_mean=round(sum(impr) / len(impr), 4),
        delta=round(delta, 4),
        ci_low=round(lo, 4),
        ci_high=round(hi, 4),
        significant=significant,
        direction=direction,
    )


METRICS = [
    "recall_at_1",
    "recall_at_3",
    "recall_at_5",
    "recall_at_10",
    "precision_at_5",
    "ndcg_at_5",
    "mrr",
    "document_recall",
    "required_fact_coverage",
    "citation_validity",
    "citation_precision_doc",
    "claim_citation_coverage",
]

COUNTERS = [
    "n_fabricated",
    "n_non_authoritative",
    "forbidden_claims",
]


@dataclass
class Comparison:
    split: str
    baseline_run: str
    improved_run: str
    n_cases: int
    metrics: list[MetricComparison] = field(default_factory=list)
    counters: dict[str, dict[str, int]] = field(default_factory=dict)
    abstention: dict[str, Any] = field(default_factory=dict)
    per_category: dict[str, Any] = field(default_factory=dict)
    latency: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "split": self.split,
            "baseline_run": self.baseline_run,
            "improved_run": self.improved_run,
            "n_cases": self.n_cases,
            "metrics": [m.to_dict() for m in self.metrics],
            "counters": self.counters,
            "abstention": self.abstention,
            "per_category": self.per_category,
            "latency": self.latency,
            "provenance": self.provenance,
        }


def build_comparison(
    baseline_trace: Path,
    improved_trace: Path,
    *,
    resamples: int = 10000,
    seed: int = 20260806,
) -> Comparison:
    base = {r["case_id"]: r for r in read_traces(baseline_trace) if not r["errors"]}
    impr = {r["case_id"]: r for r in read_traces(improved_trace) if not r["errors"]}
    shared = sorted(set(base) & set(impr))

    any_base = next(iter(base.values()))
    any_impr = next(iter(impr.values()))

    comparison = Comparison(
        split=any_base["split"],
        baseline_run=any_base["run_id"],
        improved_run=any_impr["run_id"],
        n_cases=len(shared),
    )

    comparison.metrics = [
        compare_metric(m, base, impr, resamples=resamples, seed=seed) for m in METRICS
    ]
    comparison.metrics = [m for m in comparison.metrics if m.n_paired >= 3]

    # Counters are summed, not averaged: "how many fabricated citations were
    # there" is a count, and a mean over cases would obscure that three cases
    # producing one each is the same problem as one case producing three.
    comparison.counters = {
        name: {
            "baseline": sum(base[c]["metrics"].get(name, 0) or 0 for c in shared),
            "improved": sum(impr[c]["metrics"].get(name, 0) or 0 for c in shared),
        }
        for name in COUNTERS
    }

    def confusion(source: dict) -> dict[str, int]:
        return dict(
            Counter(
                f"{source[c]['metrics'].get('abstention_expected')}"
                f"->{source[c]['metrics'].get('abstention_observed')}"
                for c in shared
            )
        )

    comparison.abstention = {
        "baseline_confusion": confusion(base),
        "improved_confusion": confusion(impr),
        "baseline_accuracy": round(
            sum(1 for c in shared if base[c]["metrics"].get("abstention_correct")) / len(shared), 4
        ),
        "improved_accuracy": round(
            sum(1 for c in shared if impr[c]["metrics"].get("abstention_correct")) / len(shared), 4
        ),
    }

    categories = sorted({base[c]["category"] for c in shared})
    comparison.per_category = {}
    for category in categories:
        ids = [c for c in shared if base[c]["category"] == category]
        def mean(source, metric, ids=ids):
            vals = [
                source[c]["metrics"].get(metric)
                for c in ids
                if isinstance(source[c]["metrics"].get(metric), (int, float))
            ]
            return round(sum(vals) / len(vals), 4) if vals else None

        comparison.per_category[category] = {
            "n": len(ids),
            "baseline_recall_at_5": mean(base, "recall_at_5"),
            "improved_recall_at_5": mean(impr, "recall_at_5"),
            "baseline_fact_coverage": mean(base, "required_fact_coverage"),
            "improved_fact_coverage": mean(impr, "required_fact_coverage"),
        }

    def latency_stats(source: dict) -> dict[str, Any]:
        values = sorted(source[c]["latency_ms"] for c in shared)
        hits = sum(1 for c in shared if source[c]["cache_hit"])
        return {
            "p50_ms": round(values[len(values) // 2], 1),
            "p95_ms": round(values[min(int(len(values) * 0.95), len(values) - 1)], 1),
            "mean_ms": round(sum(values) / len(values), 1),
            "cache_hit_rate": round(hits / len(shared), 3),
        }

    comparison.latency = {
        "baseline": latency_stats(base),
        "improved": latency_stats(impr),
        "note": (
            "p95 at this n is the second-worst observation, not a percentile estimate. "
            "Cached calls replay stored latency; read alongside cache_hit_rate."
        ),
    }

    comparison.provenance = {
        "baseline_pipeline_hash": any_base["pipeline_hash"],
        "improved_pipeline_hash": any_impr["pipeline_hash"],
        "corpus_manifest_sha": any_base["corpus_manifest_sha"],
        "dataset_id": any_base["dataset_id"],
        "generator_model": any_base["generator_model"],
        "bootstrap_resamples": resamples,
        "bootstrap_seed": seed,
        "git_sha": any_base["environment"].get("git_sha"),
    }
    return comparison


def render_markdown(c: Comparison) -> str:
    """Markdown report. Every number here comes from the Comparison object."""
    lines: list[str] = []
    a = lines.append

    a(f"# Baseline vs improved -- {c.split} split (n={c.n_cases})")
    a("")
    a(f"- baseline run: `{c.baseline_run}`")
    a(f"- improved run: `{c.improved_run}`")
    a(f"- generator: `{c.provenance['generator_model']}`")
    a(f"- corpus: `{c.provenance['corpus_manifest_sha'][:16]}`")
    a(f"- bootstrap: {c.provenance['bootstrap_resamples']:,} paired resamples, "
      f"seed {c.provenance['bootstrap_seed']}")
    a("")
    a("All intervals are 95% paired bootstrap CIs on the per-case difference. "
      "**An interval containing zero is reported as no measurable difference, "
      "not as an improvement.**")
    a("")

    a("## Deterministic metrics")
    a("")
    a("| Metric | n | Baseline | Improved | Delta | 95% CI | Verdict |")
    a("|---|---:|---:|---:|---:|:---:|---|")
    for m in c.metrics:
        ci = f"[{m.ci_low:+.3f}, {m.ci_high:+.3f}]" if m.ci_low is not None else "-"
        verdict = {
            "improved": "**improved**",
            "regressed": "**REGRESSED**",
            "no measurable difference": "no measurable difference",
        }.get(m.direction, m.direction)
        a(f"| {m.metric} | {m.n_paired} | {m.baseline_mean:.3f} | {m.improved_mean:.3f} "
          f"| {m.delta:+.3f} | {ci} | {verdict} |")
    a("")

    a("## Counts (summed over cases, not averaged)")
    a("")
    a("| Counter | Baseline | Improved | Change |")
    a("|---|---:|---:|---:|")
    for name, v in c.counters.items():
        delta = v["improved"] - v["baseline"]
        flag = " <- worse" if delta > 0 else ""
        a(f"| {name} | {v['baseline']} | {v['improved']} | {delta:+d}{flag} |")
    a("")

    a("## Abstention behaviour")
    a("")
    a(f"Accuracy: baseline {c.abstention['baseline_accuracy']:.3f}, "
      f"improved {c.abstention['improved_accuracy']:.3f}")
    a("")
    a("| expected -> observed | Baseline | Improved |")
    a("|---|---:|---:|")
    keys = sorted(set(c.abstention["baseline_confusion"]) | set(c.abstention["improved_confusion"]))
    for k in keys:
        a(f"| `{k}` | {c.abstention['baseline_confusion'].get(k, 0)} "
          f"| {c.abstention['improved_confusion'].get(k, 0)} |")
    a("")

    a("## Per category")
    a("")
    a("| Category | n | Base recall@5 | Impr recall@5 | Base facts | Impr facts |")
    a("|---|---:|---:|---:|---:|---:|")
    for name, v in sorted(c.per_category.items()):
        def fmt(x):
            return f"{x:.3f}" if isinstance(x, float) else "-"
        a(f"| {name} | {v['n']} | {fmt(v['baseline_recall_at_5'])} "
          f"| {fmt(v['improved_recall_at_5'])} | {fmt(v['baseline_fact_coverage'])} "
          f"| {fmt(v['improved_fact_coverage'])} |")
    a("")
    a("Categories with n below about 4 cannot support an interval; their rows are "
      "shown for completeness and should not be read as effects.")
    a("")

    a("## Latency")
    a("")
    a("| | p50 ms | p95 ms | mean ms | cache hit rate |")
    a("|---|---:|---:|---:|---:|")
    for arm in ("baseline", "improved"):
        s = c.latency[arm]
        a(f"| {arm} | {s['p50_ms']} | {s['p95_ms']} | {s['mean_ms']} | {s['cache_hit_rate']} |")
    a("")
    a(f"_{c.latency['note']}_")
    a("")
    return "\n".join(lines)


def render_csv(c: Comparison) -> str:
    rows = ["metric,n_paired,baseline,improved,delta,ci_low,ci_high,significant,direction"]
    for m in c.metrics:
        rows.append(
            f"{m.metric},{m.n_paired},{m.baseline_mean},{m.improved_mean},{m.delta},"
            f"{m.ci_low},{m.ci_high},{m.significant},{m.direction}"
        )
    return "\n".join(rows) + "\n"


def write_all(c: Comparison, out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out_dir / "comparison.json",
        "markdown": out_dir / "comparison.md",
        "csv": out_dir / "metrics.csv",
    }
    paths["json"].write_text(json.dumps(c.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    paths["markdown"].write_text(render_markdown(c), encoding="utf-8")
    paths["csv"].write_text(render_csv(c), encoding="utf-8")
    return paths
