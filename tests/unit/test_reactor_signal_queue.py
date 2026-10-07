"""A reload or shutdown asked for is carried out, whatever is going on when it arrives.

- A reload signalled while routes were on their way to a peer was dropped: the reactor
  re-armed the signal, then saw the routes and went round again, with nothing left to say
  a reload had been asked for.
- `daemon reload` and `daemon restart` wrote over a shutdown already asked for, so the
  daemon reloaded and carried on instead of stopping.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from exabgp.bgp.fsm import FSM
from exabgp.reactor.api.command import reactor as reactor_command
from exabgp.reactor.interrupt import Signal
from exabgp.reactor.loop import Reactor
from exabgp.reactor.peer import Peer
from exabgp.rib import RIB
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration as Parsed
from tests import negotiation

SERVICE = 'helper'


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Neighbor takes a RIB out of a process wide cache, so each test gets its own."""
    monkeypatch.setattr(RIB, '_cache', {})


def neighbor_with_a_route() -> Neighbor:
    """A neighbour as the configuration builds it, its RIB holding one route to announce."""
    parsed = Parsed(
        [
            """neighbor 192.0.2.1 {
            router-id 192.0.2.2;
            local-address 192.0.2.2;
            local-as 65001;
            peer-as 65002;
            family { ipv4 unicast; }
            static { route 10.9.9.0/24 next-hop 192.0.2.1; }
        }"""
        ],
        text=True,
    )
    assert parsed.reload(), str(parsed.error)
    neighbor = next(iter(parsed.neighbors.values()))
    for route in neighbor.routes:
        neighbor.rib.outgoing.add_to_rib(route)
    assert neighbor.rib.outgoing.pending()
    return neighbor


class Configuration:
    """What the reactor asks of its configuration on a reload, counting the reloads."""

    def __init__(self) -> None:
        self.reloads = 0
        self.processes: dict[str, Any] = {}
        self.neighbors: dict[str, Any] = {}
        self.error = ''

    def reload(self) -> bool:
        self.reloads += 1
        return False


def reactor_sending_routes() -> tuple[Reactor, Peer, Configuration]:
    reactor, _ = negotiation.reactor()
    configuration = Configuration()
    reactor.configuration = configuration
    peer = Peer(neighbor_with_a_route(), reactor)
    reactor._peers = {'peer': peer}
    peer.fsm.change(FSM.ESTABLISHED)
    return reactor, peer, configuration


@pytest.mark.parametrize('signal', [Signal.RELOAD, Signal.FULL_RELOAD], ids=['reload', 'full reload'])
def test_a_reload_waits_for_the_routes_then_happens(signal: int) -> None:
    reactor, peer, configuration = reactor_sending_routes()
    reactor.signal.received = signal

    assert reactor._signalled() == Signal.NONE
    assert configuration.reloads == 0, 'the routes were still on their way'
    assert reactor._signalled() == Signal.NONE

    peer.neighbor.rib.outgoing.clear()
    assert not peer.neighbor.rib.outgoing.pending()

    assert reactor._signalled() == signal
    assert configuration.reloads == 1
    assert reactor._signalled() == Signal.NONE
    assert configuration.reloads == 1, 'one reload asked for, one done'


def test_a_full_reload_is_not_downgraded_by_a_reload_after_it() -> None:
    reactor, peer, configuration = reactor_sending_routes()
    reactor.signal.received = Signal.FULL_RELOAD
    reactor._signalled()
    reactor.signal.received = Signal.RELOAD
    reactor._signalled()
    peer.neighbor.rib.outgoing.clear()

    assert reactor._signalled() == Signal.FULL_RELOAD


def test_a_peer_with_no_session_does_not_hold_a_reload_back() -> None:
    """Its routes stay queued until it connects, which may be never."""
    reactor, peer, configuration = reactor_sending_routes()
    peer.fsm.change(FSM.ACTIVE)
    reactor.signal.received = Signal.RELOAD

    assert reactor._signalled() == Signal.RELOAD
    assert configuration.reloads == 1


def test_a_shutdown_does_not_wait_for_the_routes() -> None:
    reactor, _, _ = reactor_sending_routes()
    reactor.signal.received = Signal.SHUTDOWN

    assert reactor._signalled() == Signal.SHUTDOWN


# ------------------------------------------------------------------- the API asking for one


def answering_reactor() -> Reactor:
    reactor, _ = negotiation.reactor()
    processes = reactor.processes
    processes._process[SERVICE] = cast(Any, None)
    processes._ack[SERVICE] = True
    processes._ackjson[SERVICE] = False
    processes._async_mode = True
    return reactor


def answers(reactor: Reactor) -> list[str]:
    return [line.decode('ascii').rstrip('\n') for line in reactor.processes._write_queue.get(SERVICE, [])]


@pytest.mark.parametrize('command', [reactor_command.reload, reactor_command.restart], ids=['reload', 'restart'])
def test_a_shutdown_asked_for_is_not_replaced(command: Any) -> None:
    reactor = answering_reactor()
    assert reactor_command.shutdown(reactor.api, reactor, SERVICE, [], '', False)

    assert not command(reactor.api, reactor, SERVICE, [], '', False)
    assert reactor.signal.received == Signal.SHUTDOWN
    assert answers(reactor)[-1] == 'error'


@pytest.mark.parametrize(
    ('command', 'signal'),
    [(reactor_command.reload, Signal.RELOAD), (reactor_command.restart, Signal.RESTART)],
    ids=['reload', 'restart'],
)
def test_with_no_shutdown_asked_for_the_command_is_taken(command: Any, signal: int) -> None:
    reactor = answering_reactor()
    assert command(reactor.api, reactor, SERVICE, [], '', False)
    assert reactor.signal.received == signal
    assert answers(reactor)[-1] == 'done'
