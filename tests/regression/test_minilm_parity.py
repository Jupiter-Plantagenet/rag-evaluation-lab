"""Parity between the hand-rolled MiniLM pooling and the reference wrapper.

`MiniLMEmbedder`'s docstring cites this file as the reason it is safe to
implement mean pooling directly rather than through sentence-transformers. Until
now the file did not exist, so that justification rested on a test nobody had
written -- exactly the shape of defect this repository was built to expose.

Skipped by default. It needs the Tier-2 stack (torch, transformers), a
sentence-transformers install, and a model download, none of which CI has. Run
it deliberately:

    pip install -r constraints/torch-cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu
    pip install sentence-transformers
    pytest tests/regression/test_minilm_parity.py --run-network

The risk being retired is specific: attention-mask-weighted mean pooling done
wrong -- averaging over padding tokens, or normalising in the wrong order --
produces embeddings that are subtly wrong rather than obviously broken. Every
retrieval number in the frozen runs was computed with this embedder, so a pooling
error would not crash anything; it would just quietly make the results describe a
different vector space than the one claimed.
"""

from __future__ import annotations

import numpy as np
import pytest

from rag_eval.retrieval.embedders import MiniLMEmbedder

pytestmark = [pytest.mark.regression, pytest.mark.needs_local_model, pytest.mark.slow]

# Deliberately mixed lengths. Batching a short text with a long one is what
# exposes a pooling bug: if padding tokens contribute, the short text's vector
# changes depending on what it was batched with.
PARITY_TEXTS = [
    "The standard card rate is 2.9% plus $0.30 per transaction.",
    "Payouts settle on T+2 for standard accounts.",
    "An endpoint failing every delivery for seven consecutive days is disabled automatically, "
    "and the merchant is notified by email before the endpoint is turned off.",
    "Refunds.",
]

MIN_COSINE = 0.9999


def test_mean_pooling_matches_sentence_transformers() -> None:
    sentence_transformers = pytest.importorskip(
        "sentence_transformers", reason="dev-only extra; not a runtime dependency"
    )

    ours = MiniLMEmbedder().encode(PARITY_TEXTS)
    reference_model = sentence_transformers.SentenceTransformer(MiniLMEmbedder.MODEL_ID)
    reference = reference_model.encode(PARITY_TEXTS, normalize_embeddings=True)

    assert ours.shape == reference.shape

    cosines = np.sum(ours * reference, axis=1)
    worst = float(cosines.min())
    assert worst >= MIN_COSINE, (
        f"pooling has diverged from the reference implementation: worst cosine "
        f"{worst:.6f} < {MIN_COSINE}. Every retrieval number in the frozen runs "
        f"was computed with this embedder."
    )


def test_a_texts_vector_does_not_depend_on_what_it_was_batched_with() -> None:
    """The padding-contamination property, tested without the reference model."""
    embedder = MiniLMEmbedder()
    alone = embedder.encode([PARITY_TEXTS[3]])
    batched = embedder.encode(PARITY_TEXTS)[3]
    cosine = float(np.dot(alone[0], batched))
    assert cosine >= MIN_COSINE, (
        f"the short text's vector changed when batched with longer ones "
        f"(cosine {cosine:.6f}); padding tokens are contributing to the mean"
    )


def test_vectors_are_l2_normalised() -> None:
    norms = np.linalg.norm(MiniLMEmbedder().encode(PARITY_TEXTS), axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)
