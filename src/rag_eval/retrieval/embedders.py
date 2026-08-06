"""Embedding backends behind one interface.

Three implementations, each earning its place:

- ``MiniLMEmbedder``  -- the headline backend. Local, deterministic, free, and
  offline after a one-time model download, so a reviewer can reproduce every
  retrieval number without an API key.
- ``TfidfSvdEmbedder`` -- zero-download, pure scikit-learn. This is what CI runs,
  which is why CI needs no model cache, no HuggingFace token, and no network.
- ``GeminiEmbedder``  -- opt-in, for comparison against a hosted model.

``fingerprint()`` is the contract that keeps the embedding cache honest. It goes
into every cache key, so switching backends or model revisions cannot silently
reuse vectors from a different model -- a failure that would produce plausible
retrieval numbers computed against the wrong space.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

import numpy as np

from rag_eval.errors import ConfigError


class Embedder(Protocol):
    name: str
    dimension: int

    def fingerprint(self) -> str:
        """Identity of the embedding function, for cache keying."""
        ...

    def encode(self, texts: list[str], *, is_query: bool = False) -> np.ndarray:
        """Return an (n, d) float32 array of L2-normalised row vectors."""
        ...


def _l2_normalise(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.maximum(norms, 1e-12)


class MiniLMEmbedder:
    """``all-MiniLM-L6-v2`` via transformers, with mean pooling done explicitly.

    Implemented directly rather than through ``sentence-transformers``, which is
    the usual wrapper. Three reasons, in order of weight:

    1. It pins the pooling and normalisation semantics in code we own, instead of
       inheriting them from a config file inside a downloaded model directory.
       For a project whose subject is reproducibility, that seam should be
       visible.
    2. Fewer network artifacts on first run: the wrapper additionally fetches
       ``modules.json``, ``config_sentence_transformers.json`` and two more
       files, each a potential first-run failure on a machine with no cache.
    3. It is fifteen lines.

    The risk -- getting the pooling subtly wrong -- is retired by a parity test
    (``tests/regression/test_minilm_parity.py``) that asserts cosine agreement
    of at least 0.9999 against the reference implementation, with
    sentence-transformers as a dev-only extra rather than a runtime dependency.
    """

    name = "minilm"
    dimension = 384
    MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, model_id: str | None = None, batch_size: int = 32) -> None:
        self.model_id = model_id or self.MODEL_ID
        self.batch_size = batch_size
        self._tokenizer = None
        self._model = None

    def _ensure_loaded(self) -> None:
        """Lazy, so importing this module never touches torch or the network."""
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as e:  # pragma: no cover - exercised only without the extra
            raise ConfigError(
                "MiniLMEmbedder needs torch and transformers, which are Tier 2 "
                "dependencies deliberately excluded from the lock files. Install with:\n"
                "  pip install -r constraints/torch-cpu.txt "
                "--extra-index-url https://download.pytorch.org/whl/cpu\n"
                "Or set embedder.kind=tfidf_svd, which needs no download."
            ) from e

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        self._model = AutoModel.from_pretrained(self.model_id)
        self._model.eval()
        # Single-threaded: CPU reductions are order-dependent, so thread count
        # changes the low bits of the output. Determinism beats speed here.
        torch.set_num_threads(1)

    def fingerprint(self) -> str:
        return f"minilm:{self.model_id}:meanpool:l2"

    def encode(self, texts: list[str], *, is_query: bool = False) -> np.ndarray:
        self._ensure_loaded()
        assert self._model is not None and self._tokenizer is not None
        torch = self._torch

        out: list[np.ndarray] = []
        with torch.inference_mode():
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                enc = self._tokenizer(
                    batch, padding=True, truncation=True, max_length=256, return_tensors="pt"
                )
                hidden = self._model(**enc).last_hidden_state

                # Attention-mask-weighted mean pooling: padding tokens must not
                # contribute, or a short text batched with a long one gets a
                # different vector than the same text encoded alone.
                mask = enc["attention_mask"].unsqueeze(-1).float()
                pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                out.append(pooled.cpu().numpy().astype(np.float32))

        return _l2_normalise(np.vstack(out) if out else np.zeros((0, self.dimension), np.float32))


class TfidfSvdEmbedder:
    """TF-IDF then truncated SVD (latent semantic analysis). Zero downloads.

    This is what CI runs. It is genuinely weaker than MiniLM at matching
    paraphrases, and the report says so rather than presenting it as equivalent.
    What it provides is a fully deterministic, dependency-light dense retriever
    so that the *entire* retrieval evaluation can run offline in CI, with real
    metrics rather than skipped tests.

    Must be fitted on the corpus before use -- unlike a pretrained model, the
    vocabulary is data-dependent. ``fingerprint()`` therefore includes a hash of
    the fitted vocabulary, so vectors cannot be reused across corpora.
    """

    name = "tfidf_svd"

    def __init__(self, dimension: int = 256, seed: int = 20260806) -> None:
        self.dimension = dimension
        self.seed = seed
        self._vectoriser = None
        self._svd = None
        self._fit_sha = "unfitted"

    def fit(self, corpus_texts: list[str]) -> TfidfSvdEmbedder:
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectoriser = TfidfVectorizer(
            lowercase=True, sublinear_tf=True, ngram_range=(1, 2), min_df=1, strip_accents="unicode"
        )
        matrix = self._vectoriser.fit_transform(corpus_texts)

        n_components = min(self.dimension, max(2, min(matrix.shape) - 1))
        self._svd = TruncatedSVD(n_components=n_components, random_state=self.seed)
        self._svd.fit(matrix)
        self.dimension = n_components

        h = hashlib.sha256()
        for term in sorted(self._vectoriser.vocabulary_):
            h.update(term.encode("utf-8"))
        self._fit_sha = h.hexdigest()[:16]
        return self

    def fingerprint(self) -> str:
        return f"tfidf_svd:d{self.dimension}:seed{self.seed}:vocab{self._fit_sha}"

    def encode(self, texts: list[str], *, is_query: bool = False) -> np.ndarray:
        if self._vectoriser is None or self._svd is None:
            raise ConfigError("TfidfSvdEmbedder.fit() must be called before encode()")
        if not texts:
            return np.zeros((0, self.dimension), np.float32)
        reduced = self._svd.transform(self._vectoriser.transform(texts)).astype(np.float32)
        return _l2_normalise(reduced)


class GeminiEmbedder:
    """Hosted embeddings via google-genai. Opt-in, never the default.

    Every call costs money and needs network, so a reviewer cannot reproduce
    numbers computed with it. Available for comparison, not for the headline.
    """

    name = "gemini"
    dimension = 3072

    def __init__(self, model: str = "models/gemini-embedding-001") -> None:
        self.model = model
        self._client = None

    def fingerprint(self) -> str:
        return f"gemini:{self.model}"

    def _ensure_client(self) -> None:
        # Constructed lazily: genai.Client(api_key=None) raises at construction,
        # so an eager client would make this module unimportable in CI.
        if self._client is not None:
            return
        import os

        from google import genai

        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise ConfigError("GeminiEmbedder requires GEMINI_API_KEY")
        self._client = genai.Client(api_key=key)

    def encode(self, texts: list[str], *, is_query: bool = False) -> np.ndarray:
        self._ensure_client()
        assert self._client is not None
        task = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
        vectors: list[list[float]] = []
        for text in texts:
            resp = self._client.models.embed_content(
                model=self.model, contents=text, config={"task_type": task}
            )
            vectors.append(list(resp.embeddings[0].values))
        return _l2_normalise(np.asarray(vectors, dtype=np.float32))


def build_embedder(kind: str, **kwargs: object) -> Embedder:
    if kind == "minilm":
        return MiniLMEmbedder(model_id=kwargs.get("model_id"))  # type: ignore[arg-type]
    if kind == "tfidf_svd":
        return TfidfSvdEmbedder(
            dimension=int(kwargs.get("dimension", 256)),
            seed=int(kwargs.get("seed", 20260806)),
        )
    if kind == "gemini":
        return GeminiEmbedder(model=str(kwargs.get("model", "models/gemini-embedding-001")))
    raise ConfigError(f"unknown embedder: {kind!r}")
