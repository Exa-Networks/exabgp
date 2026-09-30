"""Neighbor displays preserve unknown capabilities until an OPEN has been received."""

import pytest

from exabgp.bgp.neighbor.neighbor import NeighborTemplate
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from exabgp.util.enumeration import TriState
from tests import negotiation


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


@pytest.mark.parametrize('configured', [TriState.UNSET, TriState.TRUE, TriState.FALSE])
def test_neighbor_without_open_preserves_unknown_capabilities(configured: TriState) -> None:
    neighbor = negotiation.neighbor()
    neighbor.add_family(negotiation.IPV4_UNICAST)
    neighbor.add_addpath(negotiation.IPV4_UNICAST)
    neighbor.capability.asn4 = configured
    peer, _ = negotiation.peer(neighbor)

    data = peer.cli_data()
    rendered = NeighborTemplate.as_dict(data)
    family = 'ipv4 unicast'
    assert rendered['local']['capabilities']['asn4'] is configured.to_bool()
    assert rendered['peer']['capabilities']['asn4'] is None
    assert rendered['peer']['families'][family] is None
    assert rendered['local']['add-path'][family] is None
    assert rendered['peer']['add-path'][family] is None
    assert rendered['capabilities'] == []
    assert rendered['families'] == []
    assert rendered['add-path'][family] == 'disabled'
    expected = {TriState.UNSET: 'n/a', TriState.TRUE: 'enabled', TriState.FALSE: 'disabled'}[configured]
    extensive = NeighborTemplate.formated_dict(data)
    asn4_line = next(line for line in extensive['capabilities'].splitlines() if 'asn4:' in line)
    assert asn4_line.split() == ['asn4:', expected, 'n/a']
    assert extensive['families'].split() == ['ipv4', 'unicast:', 'enabled', 'n/a', 'disabled']


@pytest.mark.parametrize('send,receive', [(False, False), (True, False), (False, True), (True, True)])
def test_neighbor_reports_negotiated_addpath_directions(send: bool, receive: bool) -> None:
    neighbor = negotiation.neighbor()
    neighbor.add_family(negotiation.IPV4_UNICAST)
    peer, _ = negotiation.peer(neighbor)
    proto = Protocol(peer)
    peer.proto = proto
    proto.negotiated.sent(negotiation.open_message())
    proto.negotiated.received(negotiation.open_message())
    proto.negotiated.families = [negotiation.IPV4_UNICAST]
    proto.negotiated.addpath._send[negotiation.IPV4_UNICAST] = send
    proto.negotiated.addpath._receive[negotiation.IPV4_UNICAST] = receive

    data = peer.cli_data()
    rendered = NeighborTemplate.as_dict(data)
    family = 'ipv4 unicast'
    expected = {
        (False, False): 'disabled',
        (True, False): 'send',
        (False, True): 'receive',
        (True, True): 'send/receive',
    }
    assert rendered['families'] == [family]
    assert rendered['local']['add-path'][family] is send
    assert rendered['peer']['add-path'][family] is receive
    assert rendered['add-path'][family] == expected[send, receive]
    assert NeighborTemplate.formated_dict(data)['families'].split()[-1] == expected[send, receive]
