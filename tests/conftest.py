"""Test-suite hermeticity.

Every reproducibility claim this project makes depends on the test suite being
genuinely offline. "We set an environment variable" is not evidence of that --
a stray import or a forgotten client construction would still reach the network
and nobody would notice until a CI bill arrived.

So the guarantee is enforced two ways:

1. Provider keys are deleted from the environment, so a leaked secret cannot
   cause a billed call even if code tries.
2. ``socket.connect`` is monkeypatched to raise, so an attempted call fails with
   a traceback pointing at the exact line rather than succeeding quietly.

Tests that genuinely need the network must be marked, and are skipped unless
``--run-network`` is passed.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from rag_eval.errors import OfflineViolation

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_CACHE = REPO_ROOT / "tests" / "fixtures" / "cache"

_PROVIDER_KEYS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "BRAINTRUST_API_KEY",
    "HF_TOKEN",
)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-network",
        action="store_true",
        default=False,
        help="run tests that need the network, a provider key, or a model download",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip network-dependent tests unless explicitly requested.

    Implemented as a collection hook rather than ``-m "not needs_network"`` in
    addopts, because the latter is silently overridden the moment anyone passes
    their own ``-m`` on the command line (last -m wins). This composes.
    """
    if config.getoption("--run-network"):
        return
    skip = pytest.mark.skip(reason="needs --run-network")
    gated = {"needs_network", "needs_api_key", "needs_local_model"}
    for item in items:
        if gated & set(item.keywords):
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _hermetic_environment(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Delete provider keys and forbid outbound connections."""
    for key in _PROVIDER_KEYS:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("RAG_EVAL_OFFLINE", "1")
    monkeypatch.setenv("RAG_EVAL_CACHE_DIR", str(FIXTURE_CACHE))
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")

    if {"needs_network", "needs_api_key", "needs_local_model"} & set(request.keywords):
        return

    real_connect = socket.socket.connect

    def _blocked(self, address, *args, **kwargs):  # type: ignore[no-untyped-def]
        # Unix-domain sockets and localhost are allowed: TestClient and any
        # local subprocess are not network access in the sense that matters.
        host = address[0] if isinstance(address, tuple) else str(address)
        if host in {"127.0.0.1", "::1", "localhost"}:
            return real_connect(self, address, *args, **kwargs)
        raise OfflineViolation(
            f"outbound connection to {host!r} attempted during an offline test.\n"
            f"Mark the test @pytest.mark.needs_network if it genuinely needs it, "
            f"or record a cache fixture so it can run offline."
        )

    monkeypatch.setattr(socket.socket, "connect", _blocked)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def corpus_dir(repo_root: Path) -> Path:
    return repo_root / "data" / "corpus" / "novapay"


@pytest.fixture(scope="session")
def dataset_path(repo_root: Path) -> Path:
    return repo_root / "data" / "eval" / "novapay_v1.yaml"
