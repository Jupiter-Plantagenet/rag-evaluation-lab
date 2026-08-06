"""Generators, and the caching wrapper that makes runs replayable.

``CachedGenerator`` wraps any generator and is what every pipeline actually
uses. The wrapping order matters: the cache sits *outside* the provider, so a
cache hit costs nothing and never constructs a client -- which is why importing
this module is safe in CI with no credentials.
"""

from __future__ import annotations

import os
import time
from typing import Protocol

from rag_eval.errors import ConfigError, GenerationError
from rag_eval.generation.cache import DiskCache, cache_root, is_offline, llm_cache_key
from rag_eval.types import Completion, Usage


class Generator(Protocol):
    name: str
    model: str

    def generate(self, prompt: str, *, template_sha: str = "") -> Completion: ...


class GeminiGenerator:
    """google-genai, temperature 0, no retries that would hide a failure.

    Temperature 0 is not a determinism guarantee -- the provider may still vary
    -- which is exactly why the cache exists. It reduces variance; the cache
    removes it.
    """

    name = "gemini"

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.0,
        max_output_tokens: int = 1024,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self._client = None

    @property
    def params(self) -> dict:
        return {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "top_p": 1.0,
        }

    def _ensure_client(self):
        # Lazy: genai.Client(api_key=None) raises at construction, so eager
        # creation would make this module unimportable without a key.
        if self._client is not None:
            return self._client
        if is_offline():
            raise GenerationError(
                "refusing to construct a live client while RAG_EVAL_OFFLINE=1. "
                "This is the guard that keeps 'CI needs no credentials' true."
            )
        from google import genai

        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise ConfigError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and add a key, "
                "or run against the cache with RAG_EVAL_OFFLINE=1."
            )
        self._client = genai.Client(api_key=key)
        return self._client

    def generate(self, prompt: str, *, template_sha: str = "") -> Completion:
        client = self._ensure_client()
        started = time.perf_counter()
        resp = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "temperature": self.temperature,
                "max_output_tokens": self.max_output_tokens,
                "top_p": 1.0,
            },
        )
        elapsed = (time.perf_counter() - started) * 1000.0

        u = resp.usage_metadata
        return Completion(
            text=(resp.text or "").strip(),
            usage=Usage(
                prompt_tokens=int(getattr(u, "prompt_token_count", 0) or 0),
                completion_tokens=int(getattr(u, "candidates_token_count", 0) or 0),
                total_tokens=int(getattr(u, "total_token_count", 0) or 0),
            ),
            model=self.model,
            finish_reason=str(getattr(resp.candidates[0], "finish_reason", "STOP"))
            if resp.candidates
            else "UNKNOWN",
            latency_ms=elapsed,
            cache_hit=False,
            raw_prompt=prompt,
        )


class ScriptedGenerator:
    """Replays canned completions keyed by prompt hash. For tests only.

    Deliberately NOT a "demo mode". The predecessor project's demo mode bypassed
    retrieval entirely and returned keyword-matched strings with fake citations,
    which meant the demo and the real system shared no code path -- so the demo
    proved nothing about the system. This runs the whole real pipeline and
    substitutes only the network call.
    """

    name = "scripted"

    def __init__(self, responses: dict[str, str], model: str = "scripted") -> None:
        self.responses = responses
        self.model = model

    def generate(self, prompt: str, *, template_sha: str = "") -> Completion:
        from rag_eval.generation.cache import stable_hash

        key = stable_hash({"prompt": prompt})
        if key not in self.responses:
            raise GenerationError(
                f"ScriptedGenerator has no response for prompt hash {key[:12]}.\n"
                f"  prompt starts: {prompt[:200]!r}"
            )
        return Completion(
            text=self.responses[key],
            usage=Usage(0, 0, 0),
            model=self.model,
            finish_reason="STOP",
            latency_ms=0.0,
            cache_hit=True,
            raw_prompt=prompt,
        )


class CachedGenerator:
    """Cache-first wrapper. What every pipeline actually uses.

    On a miss while offline, raises rather than falling back. That is deliberate
    and is the single most important behaviour in this module: a silent fallback
    would let CI report metrics for a system that never ran.
    """

    def __init__(self, inner: Generator, cache: DiskCache | None = None) -> None:
        self.inner = inner
        self.cache = cache or DiskCache(cache_root(), "llm")

    @property
    def name(self) -> str:
        return f"cached:{self.inner.name}"

    @property
    def model(self) -> str:
        return self.inner.model

    def generate(self, prompt: str, *, template_sha: str = "") -> Completion:
        params = getattr(self.inner, "params", {})
        key = llm_cache_key(
            provider=self.inner.name,
            model=self.inner.model,
            params=params,
            prompt=prompt,
            template_sha=template_sha,
        )

        if is_offline():
            record = self.cache.require(
                key,
                detail=f"model={self.inner.model} params={params} template_sha={template_sha}",
                prompt_prefix=prompt,
            )
            return self._from_record(record, cache_hit=True)

        record = self.cache.get(key)
        if record is not None:
            return self._from_record(record, cache_hit=True)

        completion = self.inner.generate(prompt, template_sha=template_sha)
        self.cache.put(
            key,
            {
                "text": completion.text,
                "usage": {
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens,
                },
                "model": completion.model,
                "finish_reason": completion.finish_reason,
                "latency_ms": completion.latency_ms,
                # Stored so a reviewer can audit exactly what was sent, without
                # re-deriving it from a config that may since have changed.
                "prompt": prompt,
                "template_sha": template_sha,
            },
        )
        return completion

    @staticmethod
    def _from_record(record: dict, *, cache_hit: bool) -> Completion:
        u = record.get("usage", {})
        return Completion(
            text=record["text"],
            usage=Usage(
                u.get("prompt_tokens", 0), u.get("completion_tokens", 0), u.get("total_tokens", 0)
            ),
            model=record.get("model", "unknown"),
            finish_reason=record.get("finish_reason", "STOP"),
            # The stored latency is what the ORIGINAL call took. Replayed runs
            # must not report it as their own, or the latency figures become a
            # measurement of the cache. Callers distinguish via cache_hit.
            latency_ms=float(record.get("latency_ms", 0.0)),
            cache_hit=cache_hit,
            raw_prompt=record.get("prompt", ""),
        )


def build_generator(kind: str, **kwargs: object) -> Generator:
    if kind == "gemini":
        return GeminiGenerator(
            model=str(kwargs.get("model", "gemini-2.5-flash")),
            temperature=float(kwargs.get("temperature", 0.0)),  # type: ignore[arg-type]
            max_output_tokens=int(kwargs.get("max_output_tokens", 1024)),  # type: ignore[arg-type]
        )
    if kind == "scripted":
        return ScriptedGenerator(responses=dict(kwargs.get("responses", {})))  # type: ignore[arg-type]
    raise ConfigError(f"unknown generator: {kind!r}")
