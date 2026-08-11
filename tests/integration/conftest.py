"""Shared machinery for the offline integration suite.

Two decisions here shape every test in this directory.

**The generator is frozen, not mocked away.** Tests run the real `Pipeline` over
the real chunker, embedder, retriever, context packer, claim splitter and
citation binder. Only the network call is substituted, by a generator that
returns a fixed answer. That is the difference between an integration test and
the predecessor project's "demo mode", which bypassed retrieval entirely and so
proved nothing about the system it was demonstrating.

**The embedder is `tfidf_svd`, not MiniLM.** CI deliberately installs neither
torch nor transformers, so an integration suite that needed MiniLM would be
skipped in the one environment where it has to run — and a skipped test produces
a green badge that certifies nothing.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from rag_eval.config import PipelineConfig
from rag_eval.data.loader import load_cases
from rag_eval.ingest.corpus import Corpus, load_corpus
from rag_eval.pipeline import Pipeline, build_pipeline
from rag_eval.types import Completion, EvalCase, Usage

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FIXTURE_CORPUS = FIXTURES / "corpus"
FIXTURE_DATASET = FIXTURES / "eval" / "fixture_v1.yaml"

# Answers keyed by case id. Written by hand to exercise specific binder and
# metric branches rather than to flatter the pipeline: FX-01 cites correctly,
# FX-02 is incomplete AND fabricates a label, FX-03 abstains, FX-04 is clean but
# uncited.
FROZEN_ANSWERS: dict[str, str] = {
    "FX-01": "The standard widget unit price is 47 credits per widget [C1].",
    "FX-02": (
        "A 500-widget order qualifies for the bulk tier [C1].\n"
        "The standard unit price is 47 credits [C1].\n"
        "The discount is applied at checkout [C9]."
    ),
    "FX-03": (
        "The documentation does not specify which carrier is used for domestic "
        "delivery. It states only that a single carrier handles all domestic "
        "deliveries."
    ),
    "FX-04": "Orders placed before 14:00 are dispatched the same working day.",
}


class FrozenGenerator:
    """Returns a recorded answer for the case currently under test.

    Keyed by case id rather than by prompt hash on purpose. A prompt-keyed
    generator would make every test depend on the exact retrieved context, so a
    harmless ranking change on a different platform would surface as a confusing
    cache miss rather than as the assertion that actually matters.
    """

    name = "frozen"
    model = "frozen-fixture"

    def __init__(self, answers: dict[str, str]) -> None:
        self.answers = answers
        self.case_id: str | None = None
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, template_sha: str = "") -> Completion:
        self.prompts.append(prompt)
        if self.case_id is None or self.case_id not in self.answers:
            raise AssertionError(f"FrozenGenerator has no answer for case {self.case_id!r}")
        return Completion(
            text=self.answers[self.case_id],
            usage=Usage(prompt_tokens=len(prompt.split()), completion_tokens=8, total_tokens=0),
            model=self.model,
            finish_reason="STOP",
            latency_ms=1.0,
            cache_hit=True,
            raw_prompt=prompt,
        )


@pytest.fixture(autouse=True)
def _cache_in_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point the embedding cache at tmp_path.

    The suite writes embedding vectors on a cache miss. Without this they would
    land in the committed fixture cache directory and show up as untracked
    repository changes after a test run.
    """
    monkeypatch.setenv("RAG_EVAL_CACHE_DIR", str(tmp_path / "cache"))


@pytest.fixture
def fixture_corpus() -> Corpus:
    return load_corpus(FIXTURE_CORPUS)


@pytest.fixture
def fixture_cases() -> Sequence[EvalCase]:
    corpus = load_corpus(FIXTURE_CORPUS)
    return load_cases(FIXTURE_DATASET, split="dev", corpus=corpus.bodies())


@pytest.fixture
def fixture_case_map(fixture_cases: Sequence[EvalCase]) -> dict[str, EvalCase]:
    return {c.id: c for c in fixture_cases}


def make_config(**overrides: Any) -> PipelineConfig:
    """A pipeline config that needs no download and no credentials."""
    base: dict[str, Any] = {
        "name": "fixture",
        "description": "offline integration fixture",
        "chunker": {"kind": "fixed_size", "params": {"chunk_size": 400, "chunk_overlap": 40}},
        "embedder": {"kind": "tfidf_svd", "params": {"dimension": 16}},
        "retrieval": {"kind": "dense", "top_k": 3},
        "generator": {"kind": "scripted", "params": {"responses": {}}},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = {**base[key], **value}
        else:
            base[key] = value
    return PipelineConfig(**base)


@pytest.fixture
def build_fixture_pipeline() -> Iterator[Any]:
    """Factory: build a real pipeline with the network call frozen out."""

    def _build(**overrides: Any) -> tuple[Pipeline, FrozenGenerator]:
        config = make_config(**overrides)
        pipeline = build_pipeline(config, FIXTURE_CORPUS)
        generator = FrozenGenerator(FROZEN_ANSWERS)
        # Replace the cache-wrapped provider. Everything upstream and downstream
        # of the call is the production path.
        pipeline.generator = generator
        return pipeline, generator

    yield _build
