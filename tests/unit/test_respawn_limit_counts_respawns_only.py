"""The respawn limit must count respawns, and nothing else.

`respawn_number` used to be both the switch and the limit: `5 if api.respawn else 0`. The
limit was then tested on every `_start`, so with respawning switched off the limit was zero
and the *second* start of a helper inside one counting window tripped `2 > 0`. Nothing had
died. `ProcessError` is not caught by `_start`, so it left `Processes.start()` and reached
the reactor, which answered it by shutting the daemon down with
'Problem when sending message(s) to helper program, stopping'.

An operator reaches that from two ordinary configuration reloads, which is why the window
matters: `int(time.time()) & 0xFFFFC0` is 64 seconds aligned to the wall clock, not 64
seconds since the last start, so two reloads a second apart can trip it and two a minute
apart can miss it. Time is frozen here so the test does not inherit that coin toss.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


HELPER = {'run': ['/bin/cat'], 'encoder': 'text', 'respawn': True}

# a value whose bucket has room to spare, so nothing here lands on a boundary
FROZEN_TIME = 1_700_000_000.0


@pytest.fixture
def processes(request):
    """A real Processes, with real _start, and api.respawn as the test asks."""
    respawn = getattr(request, 'param', False)
    with patch('exabgp.reactor.api.processes.getenv') as getenv:
        environment = MagicMock()
        environment.api.respawn = respawn
        environment.api.terminate = False
        environment.api.ack = True
        environment.api.version = '5.0.0'
        getenv.return_value = environment

        from exabgp.reactor.api.processes import Processes

        with patch('exabgp.reactor.api.processes.log', MagicMock()):
            with patch('exabgp.reactor.api.processes.time.time', return_value=FROZEN_TIME):
                created = Processes()
                yield created
                for name in list(created._process):
                    created._terminate(name)


def test_two_reloads_in_one_window_do_not_raise(processes):
    """The bug. Two starts of one helper in a window, respawning off, nothing died."""
    processes.start({'helper': dict(HELPER)}, False)
    assert 'helper' in processes._process

    # a full reload where the helper's configuration changed, so it is restarted
    changed = dict(HELPER, encoder='json')
    processes.start({'helper': changed}, True)

    assert 'helper' in processes._process, 'the helper was not restarted'


def test_many_reloads_in_one_window_do_not_raise(processes):
    """Six reloads is past the limit of five, and still none of them is a respawn."""
    for index in range(6):
        configuration = {'helper': dict(HELPER, encoder='json' if index % 2 else 'text')}
        processes.start(configuration, True)
    assert 'helper' in processes._process


def test_an_ordinary_start_does_not_consume_the_respawn_budget(processes):
    """Reloads must leave no trace in the counter at all."""
    processes.start({'helper': dict(HELPER)}, False)
    processes.start({'helper': dict(HELPER, encoder='json')}, True)
    assert processes._respawning.get('helper', {}) == {}, processes._respawning


@pytest.mark.parametrize('processes', [True], indirect=True)
def test_a_helper_which_keeps_dying_is_still_given_up_on(processes):
    """The limit must still do its job on the path which is actually a respawn."""
    processes.start({'helper': dict(HELPER)}, False)
    assert processes.respawn_number == 5

    for _ in range(processes.respawn_number + 1):
        if 'helper' not in processes._process:
            break
        processes._handle_problem('helper')

    assert processes._respawning['helper'] == {int(FROZEN_TIME) & processes.respawn_timemask: 6}
    assert 'helper' not in processes._process, 'a helper past its limit must not be running'


@pytest.mark.parametrize('processes', [True], indirect=True)
def test_a_respawn_within_the_limit_restarts_the_helper(processes):
    """And it must not give up early."""
    processes.start({'helper': dict(HELPER)}, False)
    first = processes._process['helper'].pid

    processes._handle_problem('helper')

    assert 'helper' in processes._process
    assert processes._process['helper'].pid != first
