"""Fixtures which apply to the whole test suite.

The tests call the application entry points in process, and those entry points set up
the daemon: they replace sys.excepthook with the ExaBGP bug reporter, and they read the
environment. None of that is undone when the test ends, so it leaks into whatever runs
pytest in the same process, mutmut and the IDE test runners among them, which then
report their own crashes as ExaBGP panics.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def restore_process_state() -> Iterator[None]:
    """Give each test back the interpreter state it was handed."""
    excepthook = sys.excepthook
    argv = list(sys.argv)
    try:
        yield
    finally:
        sys.excepthook = excepthook
        sys.argv = argv
