"""Guard the pytest plugin block in ``pyproject.toml``.

If these tests are running at all, the block already worked -- a broken plugin
would have killed the process during collection, long before any test executed.
So this file's real job is to stop someone "tidying up" the ``-p no:`` flags in
``[tool.pytest.ini_options] addopts`` later, when the reason for them is no
longer obvious.

Background: this project's venv inherits Anaconda's site-packages, where three
packages register ``pytest11`` entry points. ``web3`` 6.11.3 ships
``pytest_ethereum``, which raises on import against ``eth-typing`` 5.2.1::

    ImportError: cannot import name 'ContractName' from 'eth_typing'

Plugin autoload is a ``sys.path`` scan, not an interpreter property, so
``--system-site-packages`` inherits the hazard and no venv can escape it.

Why the fix lives in ``pyproject.toml`` and not here: ``conftest.py`` and test
modules are collected *after* ``load_setuptools_entrypoints("pytest11")``. By the
time any code in this file could run, the process would already be dead. The
mechanism that saves us is ordering inside ``Config._preparse`` -- ``addopts`` is
prepended to argv and ``-p no:NAME`` is consumed *before* autoload, and pluggy
checks ``is_blocked(name)`` before calling ``ep.load()``.
"""

from __future__ import annotations

import pytest

BLOCKED = ("pytest_ethereum", "langsmith_plugin")


@pytest.mark.unit
@pytest.mark.parametrize("name", BLOCKED)
def test_hazardous_plugin_is_blocked(pytestconfig: pytest.Config, name: str) -> None:
    """The block is active for this session."""
    assert pytestconfig.pluginmanager.is_blocked(name), (
        f"Plugin {name!r} is no longer blocked. Restore it to the `-p no:` list in\n"
        f"[tool.pytest.ini_options] addopts in pyproject.toml.\n"
        f"Without it, `pytest` crashes on import in any environment that can see\n"
        f"Anaconda's site-packages. See this module's docstring for the mechanism."
    )


@pytest.mark.unit
@pytest.mark.parametrize("name", BLOCKED)
def test_blocked_plugin_was_never_imported(pytestconfig: pytest.Config, name: str) -> None:
    """Blocking happens before ``ep.load()``, so the module must never be imported.

    This distinguishes a real block from a plugin that loaded and was then
    deregistered -- only the former prevents the ImportError.
    """
    assert pytestconfig.pluginmanager.get_plugin(name) is None, (
        f"{name!r} is registered despite being blocked, which means it was imported. "
        f"The block is not doing what this project relies on it to do."
    )


@pytest.mark.unit
def test_blocking_an_absent_plugin_is_harmless() -> None:
    """Why the same addopts line is correct on Linux CI, where web3 is absent.

    ``PluginManager.set_blocked`` records a name; it never asserts the plugin
    exists. That is what lets one setting cover both environments with no
    branching -- and branching on environment is exactly how this class of fix
    rots.
    """
    from _pytest.config import PytestPluginManager

    pm = PytestPluginManager()
    pm.set_blocked("a_plugin_that_does_not_exist")

    assert pm.is_blocked("a_plugin_that_does_not_exist")
    assert pm.get_plugin("a_plugin_that_does_not_exist") is None
