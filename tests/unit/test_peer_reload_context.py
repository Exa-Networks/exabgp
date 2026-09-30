"""Established handlers store updates in the replacement neighbor's RIB."""

import asyncio

import pytest

from exabgp.bgp.fsm import FSM
from exabgp.bgp.message import UpdateCollection
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.timer import ReceiveTimer
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from tests.negotiation import connect
from tests.negotiation import peer as real_peer

# The session runs as its own task reading a real socket, so the test polls for it to act
# on what the peer sent, bounded so that a session which never does fails the test.
POLL_SECONDS = 0.01
POLL_ROUNDS = 500


def configured():
    config = Configuration(
        [
            """neighbor 192.0.2.1 {
            router-id 192.0.2.2;
            local-address 192.0.2.2;
            local-as 65001;
            peer-as 65002;
            adj-rib-in true;
            family { ipv4 unicast; }
        }"""
        ],
        text=True,
    )
    assert config.reload(), str(config.error)
    return config, next(iter(config.neighbors.values()))


async def until(condition, what):
    """Let the session run until `condition` holds."""
    for _ in range(POLL_ROUNDS):
        if condition():
            return
        await asyncio.sleep(POLL_SECONDS)
    raise AssertionError(f'{what} did not happen within {POLL_SECONDS * POLL_ROUNDS} seconds')


@pytest.mark.asyncio
async def test_established_reload_sends_received_routes_to_current_rib(monkeypatch):
    monkeypatch.setattr(RIB, '_cache', {})
    config, before = configured()
    monkeypatch.setattr(RIB, '_cache', {})
    _, after = configured()
    before.manual_eor = after.manual_eor = True
    # decoding what this session sent, or a path written for another rule: RFC 8955 6 has its own tests
    before.enforce_first_as = False
    negotiated, _ = _negotiated(before)
    (route,) = config.parse_route_text('route 10.0.0.0/24 next-hop 192.0.2.1')
    (wire,) = UpdateCollection([RoutedNLRI(route.nlri, route.nexthop)], [], route.attributes).messages(negotiated)

    peer, _ = real_peer(before)
    peer.proto = Protocol(peer)
    peer.proto.negotiated = negotiated
    theirs = connect(peer.proto)
    peer.recv_timer = ReceiveTimer(peer.proto.connection.session, HoldTime(180), 4, 0)
    peer.fsm.change(FSM.ESTABLISHED)

    running = asyncio.ensure_future(peer._main())
    try:
        await until(lambda: peer.stats['up'] > 0 or running.done(), 'the session coming up')
        # the configuration is reloaded while the session is up, before the UPDATE arrives
        after.previous = before
        peer.reconfigure(after)
        # the next round of the loop applies the reload, then gives the handlers the neighbor
        await until(lambda: peer._neighbor is None or running.done(), 'the reload being applied')
        theirs.sendall(wire)
        await until(lambda: peer.stats['receive-update'] > 0 or running.done(), 'the UPDATE being read')
    finally:
        theirs.close()

    with pytest.raises(NetworkError):
        await running
    assert [str(route.nlri.cidr) for route in after.rib.incoming.cached_routes()] == ['10.0.0.0/24']
    assert list(before.rib.incoming.cached_routes()) == []
