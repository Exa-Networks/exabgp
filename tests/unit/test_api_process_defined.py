"""An api naming a process which does not exist refuses the configuration.

Configuration.validate() found it, and its answer was ignored: the neighbor loaded and told
no program anything. The check now runs before a reload replaces what is running, so a
reload refused for it keeps the neighbors it had.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.configuration import Configuration
from exabgp.rib import RIB

PROCESS = 'process p { run /bin/cat; } '
NEIGHBOR = 'neighbor 127.0.0.1 {{ router-id 10.0.0.1; local-address 127.0.0.1; local-as 1; peer-as 2; {api} }}'


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def _reloaded(api: str) -> Configuration:
    configuration = Configuration([PROCESS + NEIGHBOR.format(api=api)], text=True)
    configuration.reload()
    return configuration


@pytest.mark.parametrize(
    ('api', 'reason'),
    [
        ('api { processes [ undefined ]; }', "the api names the process 'undefined', which is not defined"),
        ('api { processes-match [ ^x ]; }', "no process matches '^x'"),
        ('api { processes [ p ]; processes-match [ ^p ]; }', 'processes and processes-match can not both be given'),
    ],
)
def test_an_api_which_can_not_run_is_refused(api: str, reason: str) -> None:
    configuration = _reloaded(api)
    assert str(configuration.error) == f'neighbor 127.0.0.1: {reason}'
    assert not configuration.neighbors


@pytest.mark.parametrize('api', ['api { processes [ p ]; }', 'api { processes-match [ ^p ]; }', ''])
def test_an_api_naming_a_process_is_read(api: str) -> None:
    assert _reloaded(api).neighbors


def test_a_refused_reload_keeps_what_was_running() -> None:
    good = PROCESS + NEIGHBOR.format(api='api { processes [ p ]; }')
    bad = PROCESS + NEIGHBOR.format(api='api { processes [ undefined ]; }')
    configuration = Configuration([good], text=True)
    assert configuration.reload()
    running = dict(configuration.neighbors)
    configuration._configurations = [bad]
    assert not configuration.reload()
    assert configuration.neighbors == running
