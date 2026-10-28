"""An API helper stops when ExaBGP goes away, it does not outlive it.

The helpers under etc/exabgp/run read their answers with `sys.stdin.readline()`. Once ExaBGP has
gone, stdin is at EOF and readline returns '' at once, every time. A loop waiting for `done`, as
the `status` reads do, then spins for ever on empty strings.

The functional runner kills ExaBGP when a test is retried. api-health was in its status loop on
a macOS run of the one-file binary, it outlived the run, and the runner's leftover check failed
the job. Each helper reads through `read_line()`, which exits at EOF.

Each case gives the helper the answers which take it into its status loop, then closes stdin.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

RUN = pathlib.Path(__file__).resolve().parents[2] / 'etc' / 'exabgp' / 'run'

# both sleep before their first command (2s and 1s): the rest is reading what is already there
EXIT_WITHIN = 20

STATUS_LOOP = {
    'api-health.run': '{"pong": "uuid", "active": true}\ndone\ndone\n',
    'api-simple.run': '{"version": "6.0.0"}\ndone\n{"pong": "uuid"}\ndone\n',
}


@pytest.mark.parametrize('helper', sorted(STATUS_LOOP))
def test_a_helper_exits_when_its_stdin_closes_in_the_status_loop(helper: str) -> None:
    try:
        subprocess.run(
            [sys.executable, str(RUN / helper)],
            input=STATUS_LOOP[helper],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=EXIT_WITHIN,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f'{helper} was still running {EXIT_WITHIN}s after its stdin closed')
