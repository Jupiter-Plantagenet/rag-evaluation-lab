"""Command-line entry points.

argparse rather than typer: the CLI is six verbs with plain arguments, and
argparse is in the standard library. One fewer dependency in a project whose
subject is reproducible environments is worth more than nicer help output.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from rag_eval import __version__

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS = REPO_ROOT / "data" / "corpus" / "novapay"
DEFAULT_DATASET = REPO_ROOT / "data" / "eval" / "novapay_v1.yaml"
DEFAULT_RUNS = REPO_ROOT / "runs"


def _load_dotenv(root: Path) -> None:
    """Read .env without adding python-dotenv. Never overrides a real env var."""
    path = root / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value.strip():
            os.environ.setdefault(key.strip(), value.strip())


def cmd_ingest(args: argparse.Namespace) -> int:
    from rag_eval.config import load_config
    from rag_eval.pipeline import build_pipeline

    cfg = load_config(Path(args.config))
    pipeline = build_pipeline(cfg, Path(args.corpus))
    manifest = pipeline.corpus.manifest()

    print(f"config          {cfg.name}  (pipeline_hash {cfg.pipeline_hash})")
    print(f"chunker         {cfg.chunker.kind} {cfg.chunker.params}")
    print(f"embedder        {cfg.embedder.kind}")
    print(f"documents       {manifest['n_documents']}")
    print(f"chunks          {len(pipeline.chunks)}")
    print(f"corpus manifest {manifest['manifest_sha'][:16]}")

    if args.manifest_out:
        Path(args.manifest_out).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"manifest written to {args.manifest_out}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from rag_eval.config import load_config
    from rag_eval.pipeline import build_pipeline
    from rag_eval.runner import run_split
    from rag_eval.types import Split

    _load_dotenv(REPO_ROOT)
    cfg = load_config(Path(args.config))
    split = Split.TEST if args.final else Split.DEV

    if args.final and not args.reason:
        print(
            "ERROR: --final requires --reason.\n"
            "Held-out access is logged, and a log entry without a reason is not evidence.",
            file=sys.stderr,
        )
        return 2

    print(f"pipeline {cfg.name}  split={split.value}  config_hash={cfg.config_hash}")
    pipeline = build_pipeline(cfg, Path(args.corpus))
    print(f"corpus   {len(pipeline.corpus)} docs -> {len(pipeline.chunks)} chunks\n")

    summary = run_split(
        pipeline,
        Path(args.dataset),
        split=split,
        allow_test=args.final,
        reason=args.reason or "unspecified",
        out_dir=Path(args.out),
        repo_root=REPO_ROOT,
        limit=args.limit,
    )

    print(f"\nrun_id {summary['run_id']}")
    print(f"cases  {summary['n_cases']}  errors {summary['n_errors']}")
    for key in ("recall_at_5", "mrr", "required_fact_coverage", "abstention_accuracy",
                "citation_validity", "claim_citation_coverage"):
        value = summary.get(key)
        n = summary.get(f"{key}__n")
        shown = f"{value:.3f}" if isinstance(value, float) else str(value)
        print(f"  {key:26s} {shown}" + (f"   (n={n})" if n is not None else ""))
    print(f"  fabricated citations       {summary['total_fabricated_citations']}")
    print(f"  non-authoritative citations{summary['total_non_authoritative_citations']:>3}")
    print(f"  cache hit rate             {summary['latency']['cache_hit_rate']}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    from rag_eval.reporting.compare import build_comparison, write_all

    def resolve(path: str) -> Path:
        p = Path(path)
        return p / "trace.jsonl" if p.is_dir() else p

    comparison = build_comparison(
        resolve(args.baseline),
        resolve(args.improved),
        resamples=args.resamples,
        seed=args.seed,
    )
    paths = write_all(comparison, Path(args.out))

    print(f"comparison: {comparison.split} split, n={comparison.n_cases}\n")
    for m in comparison.metrics:
        ci = f"[{m.ci_low:+.3f}, {m.ci_high:+.3f}]"
        mark = {"improved": "+", "regressed": "!", "no measurable difference": " "}.get(
            m.direction, "?"
        )
        print(
            f" {mark} {m.metric:26s} {m.baseline_mean:6.3f} -> {m.improved_mean:6.3f} "
            f"  d={m.delta:+.3f}  {ci:>18s}  {m.direction}"
        )
    print()
    for name, v in comparison.counters.items():
        d = v["improved"] - v["baseline"]
        print(f"   {name:26s} {v['baseline']:6d} -> {v['improved']:6d}   {d:+d}")
    print()
    for kind, path in paths.items():
        print(f"wrote {kind:9s} {path}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from validate_corpus import check as check_corpus
    from validate_dataset import validate as check_dataset

    errors = check_corpus(Path(args.corpus))
    errors += check_dataset(
        Path(args.dataset),
        Path(args.corpus),
        REPO_ROOT / "data" / "eval" / "schemas" / "eval_case.v1.schema.json",
    )
    if errors:
        print(f"FAILED -- {len(errors)} violation(s):", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    print("corpus and dataset OK")
    return 0


def cmd_ledger(args: argparse.Namespace) -> int:
    """Print the held-out access log -- the evidence the split stayed frozen."""
    from rag_eval.data.loader import read_test_access_ledger

    entries = read_test_access_ledger(REPO_ROOT)
    print(f"held-out split accessed {len(entries)} time(s)")
    for e in entries:
        print(f"  {e['ts']}  n={e['n_cases']:<3} {e['reason']}")
    if not entries:
        print("  (never accessed -- the split is untouched)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rag-eval", description="RAG evaluation harness")
    p.add_argument("--version", action="version", version=f"rag-eval {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="build the index and report corpus statistics")
    ingest.add_argument("--config", required=True)
    ingest.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    ingest.add_argument("--manifest-out", default=None)
    ingest.set_defaults(func=cmd_ingest)

    run = sub.add_parser("run", help="run a pipeline over a split and score it")
    run.add_argument("--config", required=True)
    run.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    run.add_argument("--dataset", default=str(DEFAULT_DATASET))
    run.add_argument("--out", default=str(DEFAULT_RUNS))
    run.add_argument("--limit", type=int, default=None)
    run.add_argument(
        "--final",
        action="store_true",
        help="use the HELD-OUT test split. Logged to runs/.test_ledger.jsonl. Requires --reason.",
    )
    run.add_argument("--reason", default=None, help="why the held-out split is being read")
    run.set_defaults(func=cmd_run)

    compare = sub.add_parser("compare", help="compare two runs with paired bootstrap CIs")
    compare.add_argument("baseline", help="baseline run directory or trace.jsonl")
    compare.add_argument("improved", help="improved run directory or trace.jsonl")
    compare.add_argument("--out", default=str(REPO_ROOT / "reports" / "comparison"))
    compare.add_argument("--resamples", type=int, default=10000)
    compare.add_argument("--seed", type=int, default=20260806)
    compare.set_defaults(func=cmd_compare)

    validate = sub.add_parser("validate", help="validate the corpus and dataset")
    validate.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    validate.add_argument("--dataset", default=str(DEFAULT_DATASET))
    validate.set_defaults(func=cmd_validate)

    ledger = sub.add_parser("ledger", help="show held-out split access history")
    ledger.set_defaults(func=cmd_ledger)

    return p


def app(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(app())
