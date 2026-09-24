"""Fixtures which apply to every unit test.

A unit test run used to truncate the history of whoever ran it.

``InteractiveCLI.__init__`` resolves its readline history file to ``~/.exabgp_history``
and registers an ``atexit`` handler which writes it, and it builds a ``HistoryTracker``,
which resolves ``~/.local/state/exabgp/cli_history.json`` the same way.  Merely
constructing one in a test is therefore enough: readline's in process history is empty,
so the developer's file is replaced by nothing, either when the test calls
``_save_history`` or when the pytest process exits.  ``tests/unit/test_cli_completion.py``
and ``tests/unit/test_cli_format_prefix.py`` construct three of them between them.

Neither path has an environment variable of its own to point somewhere else; the
``exabgp_cli_history`` variable only switches the tracker off, which would also switch off
what those tests are there to exercise.  What both paths do share is ``$HOME``:
``os.path.expanduser('~')`` and ``pathlib.Path.home()`` read it on every call, so handing
each test its own home redirects every file either of them will ever resolve, including
the ones a test written next year will reach for.  That is why this is an autouse fixture
on the whole of ``tests/unit`` rather than an argument each test has to remember to ask
for, and why it lives here rather than beside the CLI tests: the two modules which do the
damage sit in ``tests/unit`` itself, not in ``tests/unit/cli``.

``XDG_STATE_HOME`` and ``XDG_CONFIG_HOME`` are removed rather than pointed at the
temporary home because ``HistoryTracker`` prefers them over ``$HOME``: a developer who has
either of them set would otherwise still have their real ``cli_history.json`` rewritten.
Removing them puts the tracker back on the ``Path.home()`` fallback, which is isolated.

``tests/unit/cli/test_home_isolation.py`` is the test which fails if this fixture stops
doing its job.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Captured while this module is imported, which is before any fixture has run, so it is
# the home directory pytest itself was started with rather than a redirected one.
_REAL_HOME = Path(os.path.expanduser('~'))


@pytest.fixture
def real_home() -> Path:
    """The home directory pytest was started with, for tests which must not touch it."""
    return _REAL_HOME


@pytest.fixture(autouse=True)
def isolate_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Give each test its own home directory, so none of them can write in the real one."""
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.delenv('XDG_STATE_HOME', raising=False)
    monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
    yield home
