#!/usr/bin/env python3
# encoding: utf-8

"""The test suite must hand the interpreter back as it found it

The application entry points set up a daemon rather than a library: they replace
sys.excepthook with the ExaBGP bug reporter, and application/main.py rewrites
sys.argv in place while working out which subcommand was asked for. Neither is
undone when a test ends, so it leaks into whatever else runs in the same
interpreter, which then reports its own crashes as ExaBGP panics.

Ported from the session working main, where mutmut and the IDE test runners were
doing exactly that. No test on this branch reaches the mutating path today,
measured rather than assumed: running the two files which import
exabgp.application leaves both argv and excepthook untouched. So the fixture is a
guard here rather than a repair, and the reason to have it anyway is that the leak
is invisible until something else in the process misbehaves, at which point it
looks like a bug in that something else.

Main's version drives the real interceptor rather than a stand-in, which is the
half worth copying: a test which installs a lambda proves the fixture restores
lambdas. The argv half is added here because this branch's main.py mutates argv
and main's test did not cover it.

tests/conftest.py holds the fixture. This file is what says it works.
"""

import pathlib
import sys

from exabgp.debug.intercept import intercept, trace_interceptor


class TestTheExcepthook:
    """The real ExaBGP bug reporter, not a stand-in for one"""

    def test_no_earlier_test_left_it_installed(self) -> None:
        assert sys.excepthook is not intercept, 'a previous test left the ExaBGP bug reporter installed'

    def test_a_test_may_install_it(self) -> None:
        # this is the test which would have leaked it
        trace_interceptor(False)
        assert sys.excepthook is intercept

    def test_and_it_was_put_back(self) -> None:
        # relies on running after the test above, which pytest does in file order
        assert sys.excepthook is not intercept


class TestArgv:
    """application/main.py rewrites sys.argv in place, and nothing put it back"""

    def test_a_test_may_rewrite_it(self) -> None:
        sys.argv = ['rewritten-by-a-test']

    def test_and_it_was_put_back(self) -> None:
        assert sys.argv != ['rewritten-by-a-test']


def test_the_fixture_is_where_this_file_says_it_is() -> None:
    """An autouse fixture nothing imports is easy to delete, and the suite stays green

    Every assertion above passes if the fixture is removed AND no test installs
    anything, which is the state this branch is in today. So the file is asserted
    to exist as well as to work.
    """
    conftest = pathlib.Path(__file__).resolve().parent.parent / 'conftest.py'
    assert conftest.is_file(), conftest
    assert 'restore_process_state' in conftest.read_text(encoding='utf-8')
