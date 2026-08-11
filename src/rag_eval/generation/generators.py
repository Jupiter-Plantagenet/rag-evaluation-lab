"""Generators, and the caching wrapper that makes runs replayable.

``CachedGenerator`` wraps any generator and is what every pipeline actually
uses. The wrapping order matters: the cache sits *outside* the provider, so a
cache hit costs nothing and never constructs a client -- which is why importing
this module is safe in CI with no credentials.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Protocol

from rag_eval.errors import ConfigError, GenerationError, QuotaExhausted
from rag_eval.generation.cache import DiskCache, cache_root, is_offline, llm_cache_key
from rag_eval.types import Completion, Usage


class Generator(Protocol):
    name: str
    model: str

    def generate(self, prompt: str, *, template_sha: str = "") -> Completion: ...


_RETRY_HINT_RE = re.compile(r"retry in ([0-9.]+)s", re.IGNORECASE)


class GeminiGenerator:
    """google-genai, temperature 0, with quota-aware pacing.

    Temperature 0 is not a determinism guarantee -- the provider may still vary
    -- which is exactly why the cache exists. It reduces variance; the cache
    removes it.

    **On the rate limiter.** The audit of the predecessor project criticised a
    blocking ``time.sleep`` rate limiter, so it is worth being explicit about
    why one is correct here. There, the sleep ran inside an ``async def`` route
    in a web server, blocking the event loop and serialising every concurrent
    user's request. Here it runs in a synchronous batch script whose only job is
    to make N calls in order. Blocking is the intended behaviour; there is
    nothing else to do while waiting.

    The free tier permits 5 requests per minute, and a 429 response states
    exactly how long to wait. Both are used: a proactive pace so the quota is
    rarely hit, and the server's own hint when it is. Cache hits bypass this
    entirely, so a second run over the same cases is immediate.
    """

    name = "gemini"

    # Class-level, because the quota is per project rather than per object --
    # separate generator instances share one budget.
    _last_call_at: float = 0.0
    # Circuit breaker state. Class-level because the quota is per project:
    # one case failing is noise, several in a row is a spent daily budget.
    _consecutive_exhaustions: int = 0

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.0,
        max_output_tokens: int = 1024,
        min_interval_s: float = 4.0,
        max_retries: int = 3,
        breaker_threshold: int = 3,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        # 12.5s ~= 5 requests/minute with headroom. Overridable for paid tiers.
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self.breaker_threshold = breaker_threshold
        # Any, not a concrete client type: google-genai is an optional dependency
        # and this module must stay importable in CI, which installs no provider.
        self._client: Any = None

    def _pace(self) -> None:
        """Space live calls so the quota is rarely hit in the first place."""
        elapsed = time.monotonic() - GeminiGenerator._last_call_at
        wait = self.min_interval_s - elapsed
        if wait > 0:
            time.sleep(wait)
        GeminiGenerator._last_call_at = time.monotonic()

    @property
    def params(self) -> dict[str, Any]:
        return {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "top_p": 1.0,
        }

    def _ensure_client(self) -> Any:
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

    def generate(self, prompt: str, *, template_sha: str = "") -> Completion:  # noqa: ARG002 - Generator protocol; the cache wrapper consumes template_sha
        client = self._ensure_client()
        config = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "top_p": 1.0,
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._pace()
            started = time.perf_counter()
            try:
                resp = client.models.generate_content(
                    model=self.model, contents=prompt, config=config
                )
                break
            except Exception as e:
                message = str(e)
                if "RESOURCE_EXHAUSTED" not in message and "429" not in message:
                    raise
                last_error = e
                if attempt == self.max_retries:
                    GeminiGenerator._consecutive_exhaustions += 1
                    if GeminiGenerator._consecutive_exhaustions >= self.breaker_threshold:
                        raise QuotaExhausted(
                            f"{GeminiGenerator._consecutive_exhaustions} consecutive cases "
                            f"exhausted their retries. This is a DAILY quota, not a "
                            f"per-minute window -- the 'retry in Ns' hint above is "
                            f"misleading and waiting will not help.\n"
                            f"  Daily quotas reset at midnight Pacific.\n"
                            f"  Completed work is cached, so re-running resumes where this "
                            f"stopped and makes no calls for cases already done.\n"
                            f"  See docs/model-budget.md for the measured limits.\n\n"
                            # Full body, not truncated: an earlier 300-character cap
                            # cut off the quota METRIC NAME, which was the one piece
                            # of information that identified which limit was hit.
                            f"{message}"
                        ) from e
                    raise GenerationError(
                        f"quota exhausted after {self.max_retries + 1} attempts.\n{message}"
                    ) from e

                # Honour the server's hint, but cap it. An uncapped hint on a
                # daily quota can be arbitrarily long, and the circuit breaker
                # above is the mechanism that actually resolves that case.
                hint = _RETRY_HINT_RE.search(message)
                delay = min(float(hint.group(1)) + 1.0, 65.0) if hint else 15.0 * (2**attempt)
                print(f"    quota hit; waiting {delay:.0f}s (attempt {attempt + 1})", flush=True)
                time.sleep(delay)
        else:  # pragma: no cover - loop always breaks or raises
            raise GenerationError(str(last_error))

        elapsed = (time.perf_counter() - started) * 1000.0
        GeminiGenerator._consecutive_exhaustions = 0  # a success clears the breaker

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

    def generate(self, prompt: str, *, template_sha: str = "") -> Completion:  # noqa: ARG002 - Generator protocol
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

        cached = self.cache.get(key)
        if cached is not None:
            return self._from_record(cached, cache_hit=True)

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
    def _from_record(record: dict[str, Any], *, cache_hit: bool) -> Completion:
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


def build_generator(kind: str, **kwargs: Any) -> Generator:
    if kind == "gemini":
        return GeminiGenerator(
            model=str(kwargs.get("model", "gemini-2.5-flash")),
            temperature=float(kwargs.get("temperature", 0.0)),
            max_output_tokens=int(kwargs.get("max_output_tokens", 1024)),
        )
    if kind == "scripted":
        return ScriptedGenerator(responses=dict(kwargs.get("responses", {})))
    raise ConfigError(f"unknown generator: {kind!r}")
