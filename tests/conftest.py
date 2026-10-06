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

RIB._cache is process wide on purpose: a daemon reloading its configuration finds each
neighbour's RIB by name and keeps the routes the API gave it.  Across tests that means a
neighbour named like one an earlier test configured inherits that test's routes.  Measured:
after test_configuration_export loaded conf-no-asn4.conf, `exabgp encode` run in process
printed its own UPDATE and that file's static route as well, and test_otc_parsing decoded
the second message as garbage.

Logging is process wide too.  `exabgp validate --verbose`, run in process, turns every log
source on at DEBUG and leaves it on: the environment it edits and the logger options it
loads are both singletons.  Measured: after tests/unit/application/test_validate.py, the
UPDATE handler tests in the same worker failed with "'dict' object has no attribute
'session'", because the parser now formatted every decoded UPDATE as JSON for a debug line
and their mock neighbour is a dict.  Which tests failed depended on how xdist shared the
files out, so it looked like a flaky test rather than a leak.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator

import pytest

from exabgp.environment import getenv
from exabgp.logger import log
from exabgp.logger.option import option
from exabgp.rib import RIB


class _LoggingState:
    """What log.init() and `validate --verbose` change: the logger options, the logger, the environment."""

    def __init__(self) -> None:
        env = getenv()
        self.logger = option.logger
        self.formater = option.formater
        self.short = option.short
        self.level = option.level
        self.destination = option.destination
        self.sources = dict(option.option)
        self.logit = dict(option.logit)
        self.log_function = log.logger
        # every section, not only log and debug: `exabgp decode` sets bgp.passive, and every
        # Peer a later test built would then wait for a connection rather than open one
        self.env_sections = {name: dict(section._values) for name, section in env._sections().items()}

    def restore(self) -> None:
        env = getenv()
        option.logger = self.logger
        option.formater = self.formater
        option.short = self.short
        option.level = self.level
        option.destination = self.destination
        option.option = dict(self.sources)
        option.logit = dict(self.logit)
        # the logger is a class attribute holding a function, which mypy reads as a method
        setattr(log, 'logger', self.log_function)
        for name, section in env._sections().items():
            section._values.clear()
            section._values.update(self.env_sections[name])


@pytest.fixture(autouse=True)
def restore_process_state() -> Iterator[None]:
    """Give each test back the interpreter state it was handed."""
    excepthook = sys.excepthook
    argv = list(sys.argv)
    cwd = os.getcwd()
    umask = os.umask(0o022)
    os.umask(umask)
    ribs = dict(RIB._cache)
    logging_state = _LoggingState()
    try:
        yield
    finally:
        sys.excepthook = excepthook
        sys.argv = argv
        os.umask(umask)
        RIB._cache.clear()
        RIB._cache.update(ribs)
        logging_state.restore()
        try:
            os.chdir(cwd)
        except OSError:
            # the directory the test started in was removed by the test itself; there is
            # nowhere correct to return to, and saying so beats chdir'ing somewhere else
            pass
