"""`exabgp version` says whether the message code runs compiled.

The compiled tree keeps the .py beside each extension, and a Python which did not build it
imports the .py silently, so the version output is where a user sees which one runs.
"""

from __future__ import annotations

from exabgp.application.version import build
from exabgp.bgp.message import message


def test_the_build_matches_how_the_message_code_was_loaded() -> None:
    # message.py, not the module build() looks at: both are compiled or neither is
    expected = 'python' if (message.__file__ or '').endswith('.py') else 'mypyc'
    assert build() == expected
