"""Configuration, and the hashes that make a run traceable to its inputs.

``extra="forbid"`` throughout. A typo in a config key must be an error, not a
silently ignored setting -- the failure mode otherwise is a run that reports
metrics for a configuration nobody intended, with nothing anywhere indicating
the requested change did not take effect.

Two distinct hashes, because they answer different questions:

- ``config_hash``   -- "which configuration produced this run?" Covers the whole
  resolved config.
- ``pipeline_hash`` -- "would this configuration produce the same OUTPUT?" Covers
  only fields that affect results, so changing a run label or an output path
  does not invalidate a cache or make two comparable runs look different.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.errors import ConfigError


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ChunkerConfig(_Strict):
    kind: str = "fixed_size"
    params: dict[str, Any] = Field(default_factory=dict)


class EmbedderConfig(_Strict):
    kind: str = "tfidf_svd"
    params: dict[str, Any] = Field(default_factory=dict)


class RetrievalConfig(_Strict):
    kind: str = "dense"
    top_k: int = 4
    fetch_k: int = 30
    k_rrf: int = 60
    deduplicate: bool = False
    dedupe_threshold: float = 0.8


class GeneratorConfig(_Strict):
    kind: str = "gemini"
    prompt_template: str = "answer_with_citations.jinja"
    params: dict[str, Any] = Field(default_factory=dict)


class EvaluationConfig(_Strict):
    # How much of an evidence span a chunk must cover to count as a hit. A
    # stated methodology parameter, recorded in every manifest -- requiring full
    # containment would score correct retrievals as misses purely because of
    # where a chunk boundary happened to fall.
    hit_coverage_threshold: float = 0.5
    recall_at_k: list[int] = Field(default_factory=lambda: [1, 3, 5, 10])
    bootstrap_resamples: int = 10000

    @model_validator(mode="before")
    @classmethod
    def _discard_inert_legacy_judge_fields(cls, value: Any) -> Any:
        """Read historical configs without retaining inactive judge settings."""
        if isinstance(value, dict):
            value = dict(value)
            for name in ("judge_enabled", "judge_model", "judge_temperature"):
                value.pop(name, None)
        return value


class PipelineConfig(_Strict):
    name: str
    description: str = ""
    seed: int = 20260806
    chunker: ChunkerConfig = Field(default_factory=ChunkerConfig)
    embedder: EmbedderConfig = Field(default_factory=EmbedderConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    generator: GeneratorConfig = Field(default_factory=GeneratorConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)

    @property
    def config_hash(self) -> str:
        payload = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    @property
    def pipeline_hash(self) -> str:
        """Covers only what changes the output.

        ``name`` and ``description`` are excluded deliberately: renaming a run
        must not make it look like a different experiment, and two configs that
        differ only by label should share cached results.
        """
        payload = json.dumps(
            {
                "chunker": self.chunker.model_dump(),
                "embedder": self.embedder.model_dump(),
                "retrieval": self.retrieval.model_dump(),
                "generator": self.generator.model_dump(),
                "seed": self.seed,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def load_config(path: Path) -> PipelineConfig:
    """Load a config, resolving a single level of ``extends``.

    One level only, and deliberately so: deep inheritance chains make it hard to
    answer "what was this run's actual configuration?" from the files alone,
    which is the question a reproducibility claim depends on. The resolved
    config is written into every run directory for exactly that reason.
    """
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"config not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if parent_name := raw.pop("extends", None):
        parent_path = path.parent / parent_name
        if not parent_path.exists():
            raise ConfigError(f"{path.name} extends {parent_name!r}, which does not exist")
        parent = yaml.safe_load(parent_path.read_text(encoding="utf-8")) or {}
        if "extends" in parent:
            raise ConfigError(
                f"{parent_name} itself uses `extends`. Only one level is supported, so that "
                f"a run's effective configuration is readable from two files rather than a chain."
            )
        raw = _deep_merge(parent, raw)

    try:
        return PipelineConfig(**raw)
    except Exception as e:
        raise ConfigError(f"{path.name}: {e}") from e


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out
