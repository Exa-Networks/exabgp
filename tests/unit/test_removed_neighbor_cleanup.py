#!/usr/bin/env python3
# encoding: utf-8
"""A neighbour removed by a reload left a peer, a listening socket and a connection behind.

Reported as https://github.com/Exa-Networks/exabgp/issues/1425: a passive neighbour with
`local-address` and `listen` is commented out and the configuration reloaded.  The peer
stays in `show neighbor summary`, its port stays bound, and a connection to that port is
accepted and then left in CLOSE_WAIT forever.  Repeating it accumulates sockets.

Three separate defects, each of which leaks on its own:

1.  `Reactor.active_peers` skips a passive peer which has no connection, so such a peer is
    never given a turn.  Only a peer which runs can report that it has finished and be
    dropped from `_peers`, so `remove()` set the teardown and nothing ever acted on it.
    The same trap sits under shutdown, where the reactor waits for `_peers` to empty.

2.  `Reactor.reload` never unbinds anything.  The per-neighbour `listen` socket is created
    once, in `run()`, at startup, so a removed neighbour keeps its port and a neighbour
    added by a reload never gets one until the daemon is restarted.

3.  `Peer.handle_connection` does not look at the teardown, so a peer on its way out
    accepts a connection.  Its task then completes, the reactor drops the peer, and the
    socket it had just accepted goes with it unclosed.
"""

import asyncio
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock

import pytest

os.environ['exabgp_log_enable'] = 'false'
os.environ['exabgp_log_level'] = 'CRITICAL'

from exabgp.bgp.fsm import FSM  # noqa: E402
from exabgp.protocol.family import AFI  # noqa: E402
from exabgp.protocol.ip import IP  # noqa: E402
from exabgp.reactor.listener import Listener  # noqa: E402
from exabgp.reactor.loop import Reactor  # noqa: E402
from exabgp.reactor.network.incoming import Incoming  # noqa: E402
from exabgp.reactor.peer.peer import Peer  # noqa: E402
from exabgp.reactor.protocol import Protocol  # noqa: E402
from tests import negotiation  # noqa: E402
from tests.wire_reader import tcp_socketpair  # noqa: E402

LOCAL = IP.from_string('127.0.0.1')
PEER = IP.from_string('127.0.0.2')
# Both unprivileged: these tests bind for real, and 179 needs root.
GLOBAL_PORT = 1179
NEIGHBOR_PORT = 1180


@pytest.fixture(autouse=True)
def mock_logger() -> Any:
    """The reactor and the peer log on every path taken here."""
    from exabgp.logger.option import option

    logger = option.logger
    formater = option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger = logger
    option.formater = formater


def a_reactor() -> Reactor:
    """A real Reactor with no peer: the compiled Peer and Listener refuse anything else."""
    reactor, _ = negotiation.reactor()
    return reactor


def passive_peer(reactor: Reactor | None = None) -> Peer:
    """A passive neighbour which has never had a connection, as configured on startup."""
    configured = negotiation.api_asks(negotiation.neighbor())
    configured.session.passive = True
    return Peer(configured, a_reactor() if reactor is None else reactor)


@contextmanager
def incoming_connection() -> Iterator[Incoming]:
    """A connection the listener accepted, over a real TCP socket."""
    accepted, connecting = tcp_socketpair()
    try:
        yield Incoming(AFI.ipv4, '127.0.0.2', '127.0.0.1', accepted)
    finally:
        accepted.close()
        connecting.close()


# ============================================================================
# 1. a peer told to go away has to be given a turn, or it is never dropped
# ============================================================================


def test_a_removed_passive_peer_is_still_given_a_turn() -> None:
    """Otherwise nothing acts on the teardown and the peer is kept for the process's life.

    This is what leaves the neighbour in `show neighbor summary` after the reload, and
    what makes it vanish the moment a connection arrives: the connection gives the peer a
    proto, which is the only reason active_peers() would have returned it.
    """
    reactor = a_reactor()
    peer = passive_peer(reactor)
    reactor._peers['removed'] = peer

    assert 'removed' not in reactor.active_peers(), 'a passive peer with no connection idles, as it should'

    peer.remove()

    assert 'removed' in reactor.active_peers(), 'a removed peer was never run, so it was never dropped'


def test_a_shut_down_passive_peer_is_still_given_a_turn() -> None:
    """The reactor exits when `_peers` empties, so an unreapable peer is a hang."""
    reactor = a_reactor()
    peer = passive_peer(reactor)
    reactor._peers['down'] = peer

    peer.shutdown()

    assert 'down' in reactor.active_peers(), 'shutdown left a peer the reactor can never drop'


def test_a_peer_waiting_to_reconnect_is_left_alone() -> None:
    """reestablish() also sets a teardown, but that peer is coming back.

    A passive peer does not dial out, so running it would be pointless work every turn.
    """
    reactor = a_reactor()
    peer = passive_peer(reactor)
    reactor._peers['back-soon'] = peer

    peer.reestablish()

    assert 'back-soon' not in reactor.active_peers(), 'a peer which is coming back was made busy'


# The three below were written because mutation testing said the tests above run
# active_peers() without defending it: `and` became `or`, `continue` became `break`, and
# the key added at the end became None, and every one of those edits kept the suite green.


def test_a_peer_which_dials_out_is_active_even_with_no_connection() -> None:
    """Only a *passive* peer with no connection idles. An active one has work to do.

    Turning the `and` into an `or` parks every peer which has no connection yet, which is
    every peer at startup, and no session would ever be opened.
    """
    reactor = a_reactor()
    peer = passive_peer(reactor)
    peer.neighbor.session.passive = False
    reactor._peers['dials-out'] = peer

    assert 'dials-out' in reactor.active_peers()


def test_a_passive_peer_with_a_connection_is_active() -> None:
    """The other half of the same condition."""
    reactor = a_reactor()
    peer = passive_peer(reactor)
    peer.proto = Protocol(peer)
    reactor._peers['connected'] = peer

    assert 'connected' in reactor.active_peers()


def test_an_idle_peer_does_not_hide_the_peers_after_it() -> None:
    """The skip has to be a continue: a break drops every peer past the first idle one.

    With one peer in the dictionary the two are indistinguishable, which is why this needs
    a second peer sitting behind the one being skipped.
    """
    reactor = a_reactor()
    idle = passive_peer(reactor)
    working = passive_peer(reactor)
    working.proto = Protocol(working)
    reactor._peers['idle'] = idle
    reactor._peers['working'] = working

    assert reactor.active_peers() == {'working'}, 'a peer behind an idle one was lost'


def test_a_removed_peer_finishes_rather_than_idling() -> None:
    """The turn it is now given has to end the peer, not park it.

    The reactor drops a peer whose task has completed, so run() returning is what makes
    the peer go away. A peer which parked here would be kept for the life of the process.
    """
    peer = passive_peer()

    peer.remove()

    async def finishes() -> None:
        await asyncio.wait_for(peer.run(), timeout=5)

    asyncio.run(finishes())


# ============================================================================
# 2. the listener a removed neighbour was using has to go
# ============================================================================


def bound(listener: Listener) -> set:
    return {(local, port) for (local, port, _, _, _) in listener._sockets.values()}


def test_a_listener_no_configuration_asks_for_is_closed() -> None:
    """A removed neighbour's port stayed bound and kept accepting connections."""
    listener = Listener(a_reactor())
    assert listener.listen_on(LOCAL, PEER, NEIGHBOR_PORT, None, False)
    assert bound(listener) == {(LOCAL.top(), NEIGHBOR_PORT)}

    listener.close_unwanted(set())

    assert bound(listener) == set(), 'the socket of a removed neighbour was kept'
    assert not listener._sockets


def test_a_listener_the_configuration_still_asks_for_is_kept() -> None:
    """Neighbours share a socket per address and port, so removing one must not close it."""
    listener = Listener(a_reactor())
    assert listener.listen_on(LOCAL, PEER, NEIGHBOR_PORT, None, False)
    assert listener.listen_on(LOCAL, PEER, GLOBAL_PORT, None, False)

    listener.close_unwanted({(LOCAL.top(), GLOBAL_PORT)})

    assert bound(listener) == {(LOCAL.top(), GLOBAL_PORT)}, 'a port still in the configuration was closed'


def test_closing_the_last_listener_stops_the_service() -> None:
    """serving drives incoming(), so it has to follow the sockets which are left."""
    listener = Listener(a_reactor())
    assert listener.listen_on(LOCAL, PEER, NEIGHBOR_PORT, None, False)
    assert listener.serving

    listener.close_unwanted(set())

    assert not listener.serving


# ============================================================================
# 3. a peer on its way out must not accept a connection
# ============================================================================


def test_a_removed_peer_refuses_an_incoming_connection() -> None:
    """It cannot serve one: the next turn drops the peer and the socket goes with it.

    Accepting it is how the reported CLOSE_WAIT is created.
    """
    peer = passive_peer()
    peer.remove()

    with incoming_connection() as connection:
        denied = peer.handle_connection(connection)

    assert denied is not None, 'a peer being torn down accepted a connection'
    assert peer.proto is None, 'the connection was attached to a peer which is going away'


def test_a_live_peer_still_accepts_an_incoming_connection() -> None:
    """The refusal has to be about the teardown and nothing else."""
    peer = passive_peer()
    peer.fsm.change(FSM.IDLE)

    with incoming_connection() as connection:
        denied = peer.handle_connection(connection)

        assert denied is None
        assert peer.proto is not None
        assert peer.proto.connection is connection
