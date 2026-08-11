"""Exception hierarchy.

Each type exists because its failure mode needs to be distinguishable at a call
site, not merely reported. In particular, ``CacheMissError`` and
``OfflineViolation`` must never be caught and turned into a default value: doing
so is exactly how an evaluation harness starts silently measuring a fallback
instead of the system under test.
"""

from __future__ import annotations


class RagEvalError(Exception):
    """Base for everything this package raises deliberately."""


class ConfigError(RagEvalError):
    """A configuration file is malformed, or names a component that does not exist."""


class DatasetError(RagEvalError):
    """A case is malformed, or its ground truth cannot be resolved against the corpus."""


class CorpusError(RagEvalError):
    """A corpus document is missing, unparseable, or inconsistent with the fact ledger."""


class HeldOutSplitError(RagEvalError):
    """The held-out split was requested without an explicit, logged opt-in.

    Raised rather than warned about, because a warning in a long run scrolls past
    and the resulting numbers look entirely normal.
    """


class CacheMissError(RagEvalError):
    """A cached artifact was required but absent, in a context that forbids live calls.

    Carries enough context to fix the problem without re-running: the namespace,
    the key, the model and parameters, and a prompt prefix.

    This is deliberately fatal in CI. The tempting alternative -- skip the case,
    or fall back to a stub -- produces a green build that certifies nothing,
    because the thing that was supposed to be tested never ran.
    """

    def __init__(
        self,
        namespace: str,
        key: str,
        *,
        detail: str = "",
        prompt_prefix: str = "",
        cache_path: str = "",
    ) -> None:
        self.namespace = namespace
        self.key = key
        lines = [
            f"offline cache miss in namespace {namespace!r}",
            f"  key    : {key}",
        ]
        if cache_path:
            lines.append(f"  expected at : {cache_path}")
        if detail:
            lines.append(f"  detail : {detail}")
        if prompt_prefix:
            lines.append(f"  prompt : {prompt_prefix[:400]}")
        lines += [
            "",
            "  A miss here means the prompt, the config, or the model changed since the",
            "  fixtures were recorded -- which is real information, not noise.",
            "",
            "  Fix: re-record with `rag-eval run --config ... --record-fixtures`, or run",
            "  locally with credentials and commit the new fixture.",
        ]
        super().__init__("\n".join(lines))


class OfflineViolation(RagEvalError):  # noqa: N818 - reads as the condition, not a suffix ritual
    """Network access was attempted while the offline guard was active.

    Raised from a patched socket, so the traceback points at the exact line that
    tried to reach the network -- which is more useful than discovering after the
    fact that a "hermetic" test suite was quietly making calls.
    """


class GenerationError(RagEvalError):
    """The generator failed, or returned output that could not be parsed."""


class QuotaExhausted(GenerationError):  # noqa: N818 - names the state the caller must handle
    """A provider quota is exhausted in a way retrying cannot fix.

    Distinct from a transient rate limit, because the remedies differ entirely:
    a per-minute limit clears by waiting seconds, while a daily quota clears at
    midnight and no amount of backoff will help.

    Learned the hard way. A 429 for an exhausted DAILY quota still returns a
    'retry in 40s' hint, and honouring it produces a retry loop that cannot
    succeed -- roughly ten minutes of waiting to accomplish nothing, repeated
    per remaining case. The circuit breaker in GeminiGenerator raises this after
    several consecutive cases exhaust their retries, so the run stops and says
    what remains instead of grinding.
    """

    def __init__(self, message: str, *, completed: int = 0, remaining: int = 0) -> None:
        self.completed = completed
        self.remaining = remaining
        super().__init__(message)


class CitationParseError(GenerationError):
    """Citation markers in a generated answer could not be parsed.

    Distinct from GenerationError because it is a *measured outcome* -- the
    `format_violation` failure class -- and not an infrastructure fault. It is
    recorded in the trace and scored, not retried into silence.
    """
