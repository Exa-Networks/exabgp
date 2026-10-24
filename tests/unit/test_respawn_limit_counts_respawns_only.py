"""The respawn limit must count respawns, and nothing else.

`respawn_number` was both the switch and the limit: `5 if api.respawn else 0`. The count was
kept inside `_start`, so it was taken on every start and not only on a respawn. With
respawning switched off the limit is zero, so the *second* start of a helper inside one
counting window tripped `2 > 0` although nothing had died. `ProcessError` is not caught by
`_start`, so it left `Processes.start()` and reached the reactor, which answered it with
'Problem when sending message(s) to helper program, stopping' and exited.

On this branch `start(configuration, restart=True)` terminates and restarts every helper
without comparing the old stanza to the new, so two full reloads reached it with the
configuration completely unchanged.

The window is `int(time.time()) & 0xFFFFC0`: 64 seconds aligned to the wall clock, not 64
seconds since the last start. Two reloads a second apart could trip it and two a minute
apart could miss it, which is why it looked random. Time is frozen here.
"""

from unittest.mock import MagicMock, patch

import pytest


HELPER = {'run': ['/bin/cat'], 'encoder': 'text', 'respawn': True}

# a value whose bucket has room to spare, so nothing here lands on a boundary
FROZEN_TIME = 1700000000.0


@pytest.fixture
def processes(request):
    """A real Processes, with the real _start, and api.respawn as the test asks."""
    respawn = getattr(request, 'param', False)
    with patch('exabgp.reactor.api.processes.getenv') as getenv:
        environment = MagicMock()
        environment.api.respawn = respawn
        environment.api.terminate = False
        environment.api.ack = True
        getenv.return_value = environment

        from exabgp.reactor.api.processes import Processes

        with patch('exabgp.reactor.api.processes.log', MagicMock()):
            with patch('exabgp.reactor.api.processes.time.time', return_value=FROZEN_TIME):
                created = Processes()
                yield created
                for name in list(created._process):
                    created._terminate(name)


def test_two_reloads_in_one_window_do_not_raise(processes):
    """The bug: two full reloads, respawning off, configuration unchanged, nothing died."""
    processes.start({'helper': dict(HELPER)}, False)
    assert 'helper' in processes._process

    processes.start({'helper': dict(HELPER)}, True)

    assert 'helper' in processes._process, 'the helper was not restarted'


def test_many_reloads_in_one_window_do_not_raise(processes):
    """Six is past the limit of five, and still not one of them is a respawn."""
    for _ in range(6):
        processes.start({'helper': dict(HELPER)}, True)
    assert 'helper' in processes._process


def test_an_ordinary_start_does_not_consume_the_respawn_budget(processes):
    """A reload must leave no trace in the counter at all."""
    processes.start({'helper': dict(HELPER)}, False)
    processes.start({'helper': dict(HELPER)}, True)
    assert processes._respawning.get('helper', {}) == {}, processes._respawning


@pytest.mark.parametrize('processes', [True], indirect=True)
def test_a_helper_which_keeps_dying_is_still_given_up_on(processes):
    """The limit must still do its job on the path which really is a respawn.

    This branch lets ProcessError leave _handle_problem, which is how a helper that cannot
    stay alive stops the daemon. That is the behaviour being preserved, not changed.
    """
    processes.start({'helper': dict(HELPER)}, False)
    assert processes.respawn_number == 5

    for _ in range(processes.respawn_number):
        processes._handle_problem('helper')

    bucket = int(FROZEN_TIME) & processes.respawn_timemask
    assert processes._respawning['helper'] == {bucket: 5}

    from exabgp.reactor.api.processes import ProcessError

    with pytest.raises(ProcessError):
        processes._handle_problem('helper')

    assert 'helper' not in processes._process, 'a helper past its limit must not be running'


@pytest.mark.parametrize('processes', [True], indirect=True)
def test_a_respawn_within_the_limit_restarts_the_helper(processes):
    """And it must not give up early."""
    processes.start({'helper': dict(HELPER)}, False)
    first = processes._process['helper'].pid

    processes._handle_problem('helper')

    assert 'helper' in processes._process
    assert processes._process['helper'].pid != first
