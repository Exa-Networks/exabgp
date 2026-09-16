"""Established handlers store updates in the replacement neighbor's RIB."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from exabgp.bgp.fsm import FSM
from exabgp.bgp.message import _NOP, Update, UpdateCollection
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.reactor.peer.peer import Peer
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB


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


@pytest.mark.asyncio
async def test_established_reload_sends_received_routes_to_current_rib(monkeypatch):
    monkeypatch.setattr(RIB, '_cache', {})
    config, before = configured()
    monkeypatch.setattr(RIB, '_cache', {})
    _, after = configured()
    before.manual_eor = after.manual_eor = True
    negotiated, _ = _negotiated(before)
    (route,) = config.parse_route_text('route 10.0.0.0/24 next-hop 192.0.2.1')
    (wire,) = UpdateCollection([RoutedNLRI(route.nlri, route.nexthop)], [], route.attributes).messages(negotiated)
    update = Update.unpack_message(wire[19:], negotiated)
    assert type(update) is Update
    update.parse(negotiated)
    peer = Peer(before, Mock())
    peer.proto = Protocol(peer)
    peer.proto.negotiated = negotiated
    peer.proto.connection = Mock()
    peer.recv_timer = Mock()
    peer.fsm.change(FSM.ESTABLISHED)
    messages = iter([_NOP, update])

    async def read_message():
        message = next(messages, None)
        if message is None:
            raise EOFError
        if message is _NOP:
            after.previous = before
            peer.reconfigure(after)
        return message

    with (
        patch.object(peer.proto, 'read_message', side_effect=read_message),
        patch('exabgp.reactor.peer.peer.KA.send_if_needed', new=AsyncMock()),
        pytest.raises(EOFError),
    ):
        await peer._main()
    assert [str(route.nlri.cidr) for route in after.rib.incoming.cached_routes()] == ['10.0.0.0/24']
    assert list(before.rib.incoming.cached_routes()) == []
