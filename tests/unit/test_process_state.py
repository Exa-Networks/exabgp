"""The test suite must hand the interpreter back as it found it.

The application entry points replace sys.excepthook with the ExaBGP bug reporter. When a
test calls one of them, that hook used to stay installed for the rest of the process, so
a crash in the tool running the tests was reported as an ExaBGP panic.
"""

import sys

from exabgp.debug.intercept import intercept, trace_interceptor


def test_the_excepthook_is_restored_between_tests() -> None:
    assert sys.excepthook is not intercept, 'a previous test left the ExaBGP bug reporter installed'


def test_a_test_installing_the_excepthook_does_not_leak_it() -> None:
    """This is the test which would have leaked it, the fixture puts it back."""
    trace_interceptor(False)
    assert sys.excepthook is intercept


def test_the_excepthook_is_restored_after_the_test_which_installs_it() -> None:
    assert sys.excepthook is not intercept
