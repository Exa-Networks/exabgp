"""Fixtures which apply to the whole test suite.

The tests call the application entry points in process, and those entry points set up
the daemon: they replace sys.excepthook with the ExaBGP bug reporter, and they read the
environment. None of that is undone when the test ends, so it leaks into whatever runs
pytest in the same process, mutmut and the IDE test runners among them, which then
report their own crashes as ExaBGP panics.

The working directory and the umask leak the same way and cost more.  Reactor.__init__
builds a Daemon, and Daemon.__init__ runs os.chdir('/') and os.umask(0o137) before doing
anything else, so any test which constructs a Reactor moves the whole pytest process to /
and leaves it creating directories without an execute bit.

Measured: after such a test, pytest's own tmp_path fixture fails to make its lock file
and pytest cannot write its cache, so every LATER test using tmp_path errors at setup
rather than failing on anything it tested.  It looks like a bug in whichever test happens
to run next.  A relative path read anywhere after it resolves against / for the same
reason.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def restore_process_state() -> Iterator[None]:
    """Give each test back the interpreter state it was handed."""
    excepthook = sys.excepthook
    argv = list(sys.argv)
    cwd = os.getcwd()
    umask = os.umask(0o022)
    os.umask(umask)
    try:
        yield
    finally:
        sys.excepthook = excepthook
        sys.argv = argv
        os.umask(umask)
        try:
            os.chdir(cwd)
        except OSError:
            # the directory the test started in was removed by the test itself; there is
            # nowhere correct to return to, and saying so beats chdir'ing somewhere else
            pass
