"""Content-addressed on-disk cache for model responses.

This is what makes the project both reproducible and cheap to re-run, and it is
what lets CI replay real model outputs with no credentials.

Design decisions worth stating, because each has a tempting wrong answer:

**Files, not SQLite.** ``diskcache`` is already installed and would be less
code. But a single opaque database cannot be diffed in review, cannot have
individual entries committed as CI fixtures, and takes cross-process locks that
misbehave on Windows. Content-addressed files are all three.

**The full rendered prompt is stored in the value, not just its hash.** It
doubles the storage and it is the difference between a cache a reviewer can
audit and one they must trust. Anyone can open an entry and see exactly what was
sent.

**No TTL, ever.** A research cache that silently expires destroys
reproducibility on a timer. Entries are invalidated only by key change -- which
happens when, and only when, something that legitimately alters the output
changes: the model, a generation parameter, the prompt template, or the input.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_eval.errors import CacheMissError

CACHE_SCHEMA_VERSION = 1


def canonical_json(obj: Any) -> str:
    """Stable serialisation. Key order must not change a cache key."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def is_offline() -> bool:
    return os.environ.get("RAG_EVAL_OFFLINE", "") == "1"


@dataclass
class DiskCache:
    """Namespaced content-addressed store.

    Layout: ``<root>/<namespace>/<key[:2]>/<key>.json.gz``. The two-character
    shard keeps directories to a few thousand entries; hex-only names sidestep
    Windows' illegal-character rules and 260-character path limit.
    """

    root: Path
    namespace: str

    def __post_init__(self) -> None:
        self.root = Path(self.root)

    def path_for(self, key: str) -> Path:
        return self.root / self.namespace / key[:2] / f"{key}.json.gz"

    def get(self, key: str) -> dict | None:
        path = self.path_for(key)
        if not path.exists():
            return None
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            record = json.load(fh)

        stored = record.get("cache_schema_version")
        if stored != CACHE_SCHEMA_VERSION:
            # Raise rather than ignore. A differently-shaped record that is
            # silently reused produces results computed from a contract this
            # code no longer implements -- and nothing about them looks wrong.
            raise CacheMissError(
                self.namespace,
                key,
                detail=(
                    f"cache_schema_version {stored} != {CACHE_SCHEMA_VERSION}. "
                    f"Re-record this namespace rather than reusing entries "
                    f"written against a different contract."
                ),
                cache_path=str(path),
            )
        return record

    def put(self, key: str, value: dict) -> None:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {**value, "cache_schema_version": CACHE_SCHEMA_VERSION}

        # Write-then-rename: an interrupted run must not leave a truncated entry
        # that later reads as a valid cache hit.
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False)
        tmp.replace(path)

    def require(self, key: str, *, detail: str = "", prompt_prefix: str = "") -> dict:
        """Fetch, or raise with enough context to fix it without re-running.

        Called on the offline path. The alternative -- returning a default, or
        skipping the case -- yields a green build that certifies nothing,
        because the thing under test never ran.
        """
        record = self.get(key)
        if record is None:
            raise CacheMissError(
                self.namespace,
                key,
                detail=detail,
                prompt_prefix=prompt_prefix,
                cache_path=str(self.path_for(key)),
            )
        return record

    def stats(self) -> dict[str, int]:
        base = self.root / self.namespace
        if not base.exists():
            return {"entries": 0, "bytes": 0}
        files = list(base.rglob("*.json.gz"))
        return {"entries": len(files), "bytes": sum(f.stat().st_size for f in files)}


def cache_root() -> Path:
    """``RAG_EVAL_CACHE_DIR`` if set, else ``<cwd>/cache``.

    CI points this at ``tests/fixtures/cache``, a small committed replay set.
    """
    return Path(os.environ.get("RAG_EVAL_CACHE_DIR") or (Path.cwd() / "cache"))


def llm_cache_key(
    *,
    provider: str,
    model: str,
    params: dict,
    prompt: str,
    template_sha: str,
) -> str:
    """Everything that legitimately changes a completion, and nothing else.

    Notably absent: the case id, the run id, and the timestamp. Including any of
    them would make every entry a miss and the cache pointless. Notably present:
    the template sha, so editing a prompt file invalidates its entries rather
    than silently reusing answers generated from different instructions.
    """
    return stable_hash(
        {
            "v": CACHE_SCHEMA_VERSION,
            "ns": "llm",
            "provider": provider,
            "model": model,
            "params": params,
            "template_sha": template_sha,
            "prompt": prompt,
        }
    )
