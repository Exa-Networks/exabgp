"""A RIB one test configured must not be handed to the next.

RIB._cache keeps each neighbour's RIB by name for the life of the process, which is what
lets a daemon reload without losing the routes the API gave it.  In the test suite it let
test_configuration_export leave conf-no-asn4.conf's static route in the RIB of neighbour
127.0.0.1, so test_otc_parsing, run later on the same worker, had `exabgp encode` print two
UPDATEs and failed decoding the second.  tests/conftest.py now gives every test back the
cache it started with.

Run in a subprocess: the defect is an ordering between two files, and only a fresh pytest
process with a fixed order reproduces it every time.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_a_configuration_loaded_by_one_test_does_not_reach_the_next() -> None:
    result = subprocess.run(
        [
            sys.executable,
            '-m',
            'pytest',
            '-q',
            '-p',
            'no:cacheprovider',
            '-p',
            'no:randomly',
            'tests/unit/configuration/test_configuration_export.py::test_configuration_can_be_serialized[conf-no-asn4.conf]',
            'tests/unit/test_otc_parsing.py::test_inline_encode_literal_otc',
        ],
        cwd=ROOT,
        env={**os.environ, 'exabgp_log_enable': 'false'},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout[-2000:]
