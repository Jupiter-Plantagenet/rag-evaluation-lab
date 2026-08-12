"""Fail the build if the CI environment drifts from its declared posture.

Two invariants matter enough to enforce mechanically rather than by convention:

1. **CI is torch-free.** ``torch`` on PyPI's manylinux wheels is the CUDA build,
   so a single transitive dependency leaking into ``requirements/lock/linux-py312.txt``
   would silently add ~2.5 GB of ``nvidia-*`` wheels to every CI run. The failure
   mode is a timeout, minutes from the actual mistake -- so check it directly.

2. **CI cannot reach a model provider.** The offline posture is what lets the
   badge mean something. If a key were present, a cache miss could quietly become
   a live call and the "runs with no credentials" claim would be false.

Run:  python scripts/assert_ci_env.py
"""

from __future__ import annotations

import importlib.util
import os
import sys

# Tier 2 packages. Absent from both lock files, so a clean CI environment must
# not be able to import them. They ARE importable on a machine where someone
# installed constraints/torch-cpu.txt to run the MiniLM backend, or on an
# interpreter with a system Python's packages in scope -- which is why this
# script is a CI check and is expected to fail on such a development machine.
# `faiss` is no longer a declared dependency of this project at all -- it is kept
# in the list as a regression guard, since a transitive dependency could
# reintroduce it and the symptom would again be a CI timeout far from the cause.
FORBIDDEN_IN_CI = ("torch", "transformers", "faiss", "sentence_transformers")

# If any of these is set in CI, the offline guarantee is not a guarantee.
FORBIDDEN_KEYS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "BRAINTRUST_API_KEY",
)


def main() -> int:
    failures: list[str] = []

    if importlib.util.find_spec("rag_eval") is None:
        failures.append("rag_eval is not importable -- `pip install -e . --no-deps` did not run")

    for name in FORBIDDEN_IN_CI:
        spec = importlib.util.find_spec(name)
        if spec is not None:
            failures.append(
                f"{name!r} is importable in CI (from {spec.origin}).\n"
                f"    It must stay in [project.optional-dependencies].local and out of the lock.\n"
                f"    Something added it to a requirements/*.in file, or a Tier 1 package\n"
                f"    grew a dependency on it. Check `uv pip compile` output before merging."
            )

    for key in FORBIDDEN_KEYS:
        if os.environ.get(key):
            failures.append(
                f"{key} is set in CI. The offline posture forbids provider credentials,\n"
                f"    because a cache miss would become a live billed call and the\n"
                f"    'CI needs no credentials' claim would stop being true."
            )

    if os.environ.get("RAG_EVAL_OFFLINE") != "1":
        failures.append("RAG_EVAL_OFFLINE is not '1' -- CI must run with the offline guard active")

    if failures:
        print("CI environment assertions FAILED:\n", file=sys.stderr)
        for i, f in enumerate(failures, 1):
            print(f"  {i}. {f}\n", file=sys.stderr)
        return 1

    print(
        "CI environment OK: torch-free, credential-free, offline guard active "
        f"(python {sys.version.split()[0]})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
