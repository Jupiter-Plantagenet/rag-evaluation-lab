"""Derive corrected-v2 reports from immutable stored traces; never runs a model."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATASET = ROOT / "data" / "eval" / "novapay_v1.yaml"
CORPUS = ROOT / "data" / "corpus" / "novapay"
RUNS = ROOT / "runs"


def main() -> None:
    from rag_eval.data.loader import load_all_cases
    from rag_eval.ingest.corpus import load_corpus
    from rag_eval.reporting.corrected_v2 import derive, write

    corpus = load_corpus(CORPUS)
    cases = {case.id: case for case in load_all_cases(DATASET, corpus=corpus.bodies())}
    pairs = {
        "held-out": (
            "baseline-test-20260806T182019Z-66ee099b",
            "improved-test-20260806T182251Z-1e6a1bf8",
        ),
        "dev": ("baseline-dev-20260806T180859Z-66ee099b", "improved-dev-20260806T181347Z-1e6a1bf8"),
    }
    for split, (base, impr) in pairs.items():
        payload = derive(RUNS / base / "trace.jsonl", RUNS / impr / "trace.jsonl", cases)
        write(payload, ROOT / "reports" / "corrected-v2" / split, split)
        print(f"wrote corrected-v2 {split}")


if __name__ == "__main__":
    main()
