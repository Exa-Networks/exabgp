"""api.terminate must stop the daemon when a helper dies (issue #304).

A helper which announced routes and then died leaves them announced, with nobody left
to withdraw them. api.terminate is the operator's way out: stop exabgp, close every
session, and let the peers drop the routes.

It stopped working with the move to asyncio. The only check was in Peer.run(), which
the generator engine called on every tick and which now runs once, when the peer
starts. It also only looked at helpers which failed a write, so one which simply
exited was never noticed at all.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from exabgp.reactor.interrupt import Signal
from exabgp.reactor.loop import Reactor

HELPER = {'run': ['/bin/cat'], 'encoder': 'text', 'respawn': True}


@pytest.fixture
def processes(request):
    """A real Processes, with api.respawn and api.terminate as the test asks."""
    respawn, terminate = getattr(request, 'param', (False, False))
    with patch('exabgp.reactor.api.processes.getenv') as getenv:
        environment = MagicMock()
        environment.api.respawn = respawn
        environment.api.terminate = terminate
        environment.api.ack = True
        environment.api.version = '5.0.0'
        getenv.return_value = environment

        from exabgp.reactor.api.processes import Processes

        with patch('exabgp.reactor.api.processes.log', MagicMock()):
            created = Processes()
            created.start({'helper': dict(HELPER)}, False)
            assert 'helper' in created._process
            yield created
            for name in list(created._process):
                created._terminate(name)


# ==============================================================================
# Processes knows which helpers are gone for good
# ==============================================================================


def test_a_running_helper_is_not_lost(processes) -> None:
    assert processes.lost() == []


@pytest.mark.parametrize('processes', [(False, False)], indirect=True)
def test_a_helper_which_ended_without_respawn_is_lost(processes) -> None:
    processes._handle_problem('helper')

    assert 'helper' not in processes._process
    assert processes.lost() == ['helper']


@pytest.mark.parametrize('processes', [(True, False)], indirect=True)
def test_a_respawned_helper_is_not_lost(processes) -> None:
    processes._handle_problem('helper')

    assert 'helper' in processes._process
    assert processes.lost() == []


@pytest.mark.parametrize('processes', [(True, False)], indirect=True)
def test_a_helper_past_its_respawn_limit_is_lost(processes, monkeypatch: pytest.MonkeyPatch) -> None:
    # respawns are counted per time bucket, int(time.time()) & respawn_timemask; a loop
    # which straddled a bucket boundary restarted the count and the helper was never lost,
    # which a loaded full suite run hit. The clock is held so every death lands in one bucket.
    monkeypatch.setattr(
        'exabgp.reactor.api.processes.time', SimpleNamespace(time=lambda: 1_000_000.0, sleep=time.sleep)
    )
    for _ in range(processes.respawn_number + 1):
        processes._handle_problem('helper')

    assert 'helper' not in processes._process
    assert processes.lost() == ['helper']


@pytest.mark.parametrize('processes', [(True, True)], indirect=True)
def test_terminate_wins_over_respawn(processes) -> None:
    # respawning would hide the death from the reactor, which is asked to stop on it
    processes._handle_problem('helper')

    assert 'helper' not in processes._process
    assert processes.lost() == ['helper']


@pytest.mark.parametrize('processes', [(False, False)], indirect=True)
def test_a_reload_which_starts_the_helper_again_clears_it(processes) -> None:
    processes._handle_problem('helper')
    processes.start({'helper': dict(HELPER)}, True)

    assert 'helper' in processes._process
    assert processes.lost() == []


# ==============================================================================
# The reactor shuts down on a lost helper, only when asked to
# ==============================================================================


def _reactor(terminate: bool, lost: list[str]) -> SimpleNamespace:
    processes = SimpleNamespace(terminate_on_error=terminate, lost=lambda: list(lost))
    return SimpleNamespace(_helper_lost=False, processes=processes, signal=SimpleNamespace(received=Signal.NONE))


def test_a_lost_helper_shuts_the_daemon_down_with_terminate() -> None:
    reactor = _reactor(terminate=True, lost=['helper'])

    with patch('exabgp.reactor.loop.log', MagicMock()):
        Reactor._terminate_on_lost_helper(reactor)  # type: ignore[arg-type]

    assert reactor._helper_lost
    assert reactor.signal.received == Signal.SHUTDOWN


def test_a_lost_helper_is_left_alone_without_terminate() -> None:
    reactor = _reactor(terminate=False, lost=['helper'])

    Reactor._terminate_on_lost_helper(reactor)  # type: ignore[arg-type]

    assert not reactor._helper_lost
    assert reactor.signal.received == Signal.NONE


def test_nothing_happens_while_every_helper_runs() -> None:
    reactor = _reactor(terminate=True, lost=[])

    Reactor._terminate_on_lost_helper(reactor)  # type: ignore[arg-type]

    assert not reactor._helper_lost
    assert reactor.signal.received == Signal.NONE
