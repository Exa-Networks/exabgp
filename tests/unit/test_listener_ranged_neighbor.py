"""A connection to a ranged neighbor gets a session of its own.

`neighbor 127.0.0.0/24 { passive; }` accepts any peer in the range. The listener builds one
neighbor per connection from the configured one; it used `copy.copy`, so every peer shared
the configured neighbor's Session and RIB. Setting the first peer's address rewrote the
range itself: after a connection from 127.0.0.1 the configured neighbor read 127.0.0.1, its
range started there, and each new peer overwrote the addresses of the one before.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.listener import Listener
from exabgp.reactor.loop import Reactor
from exabgp.reactor.peer import Peer

RANGED = """
neighbor 127.0.0.0/24 {
    router-id 1.1.1.1;
    local-address 127.0.0.1;
    local-as 65000;
    peer-as 65001;
    passive;
}
"""


def connect_once(tmp_path: Path) -> tuple[Reactor, str]:
    """A reactor with the ranged neighbor, after one real connection from 127.0.0.1."""
    configuration_file = tmp_path / 'ranged.conf'
    configuration_file.write_text(RANGED)
    configuration = Configuration([str(configuration_file)])
    assert configuration.reload(), configuration.error

    reactor = Reactor(None)
    (template_key, template), *rest = configuration.neighbors.items()
    assert not rest, 'the configuration has one neighbor'
    reactor.register_peer(template_key, Peer(template, reactor))

    listener = Listener(reactor)
    listener.serving = True
    with socket.create_server(('127.0.0.1', 0)) as listening:
        peer = socket.create_connection(listening.getsockname())
        accepted, _ = listening.accept()
        try:
            listener._accepted[listening] = accepted
            for _ in listener.new_connections():
                pass
        finally:
            peer.close()
    return reactor, template_key


def test_the_configured_range_is_left_as_configured(tmp_path: Path) -> None:
    reactor, template_key = connect_once(tmp_path)
    template = reactor.neighbor(template_key)
    assert template is not None
    assert str(template.session.peer_address) == '127.0.0.0'
    assert template.range_size == 256
    assert not template.ephemeral


def test_the_peer_has_its_own_session_and_rib(tmp_path: Path) -> None:
    reactor, template_key = connect_once(tmp_path)
    template = reactor.neighbor(template_key)
    assert template is not None
    added = [key for key in reactor.peers() if key != template_key]
    assert len(added) == 1, reactor.peers()
    created = reactor.neighbor(added[0])
    assert created is not None

    assert created.ephemeral
    assert created.range_size == 1
    assert str(created.session.peer_address) == '127.0.0.1'
    assert created.session is not template.session
    assert created.rib is not template.rib
    assert created.rib.name == created.name()


RANGED_WITH_ROUTES = """
neighbor 127.0.0.0/24 {
    router-id 1.1.1.1;
    local-address 127.0.0.1;
    local-as 65000;
    peer-as 65001;
    passive;
    static {
        route 192.0.2.0/24 next-hop 127.0.0.2;
        route 198.51.100.0/24 next-hop 127.0.0.3;
    }
}
"""


def accept_from(tmp_path: Path, source: str, text: str) -> tuple[Reactor, str]:
    """A reactor with the ranged neighbor of `text`, after one connection from `source`."""
    configuration_file = tmp_path / 'ranged.conf'
    configuration_file.write_text(text)
    configuration = Configuration([str(configuration_file)])
    assert configuration.reload(), configuration.error

    reactor = Reactor(None)
    (template_key, template), *rest = configuration.neighbors.items()
    assert not rest, 'the configuration has one neighbor'
    reactor.register_peer(template_key, Peer(template, reactor))

    listener = Listener(reactor)
    listener.serving = True
    with socket.create_server(('127.0.0.1', 0)) as listening:
        peer = socket.create_connection(listening.getsockname(), source_address=(source, 0))
        accepted, _ = listening.accept()
        try:
            listener._accepted[listening] = accepted
            for _ in listener.new_connections():
                pass
        finally:
            peer.close()
    return reactor, template_key


@pytest.mark.rfc('rfc4271#5.1.3-no-next-hop-of-the-peer')
def test_a_peer_of_a_range_is_not_sent_a_route_whose_next_hop_is_its_address(tmp_path: Path) -> None:
    """The range is checked when configured, the peer's own address only once it connects."""
    reactor, template_key = accept_from(tmp_path, '127.0.0.2', RANGED_WITH_ROUTES)
    template = reactor.neighbor(template_key)
    assert template is not None
    (added,) = [key for key in reactor.peers() if key != template_key]
    created = reactor.neighbor(added)
    assert created is not None
    assert str(created.session.peer_address) == '127.0.0.2'

    outgoing = created.rib.outgoing
    queued = sorted(str(route.nlri) for route in outgoing.queued_routes())
    cached = sorted(str(route.nlri) for route in outgoing.cached_routes())
    assert queued == cached == ['198.51.100.0/24']
    assert [str(route.nlri) for route in created.routes] == ['198.51.100.0/24']
    assert not outgoing._pending_withdraws.get((AFI.ipv4, SAFI.unicast)), 'the peer was never sent it to withdraw'
    assert sorted(str(route.nlri) for route in template.rib.outgoing.queued_routes()) == [
        '192.0.2.0/24',
        '198.51.100.0/24',
    ], 'the range keeps its routes for its other peers'


@pytest.mark.rfc('rfc4271#5.1.3-no-next-hop-of-the-peer', polarity='negative')
def test_another_peer_of_the_range_is_sent_both_routes(tmp_path: Path) -> None:
    reactor, template_key = accept_from(tmp_path, '127.0.0.4', RANGED_WITH_ROUTES)
    (added,) = [key for key in reactor.peers() if key != template_key]
    created = reactor.neighbor(added)
    assert created is not None

    assert sorted(str(route.nlri) for route in created.rib.outgoing.queued_routes()) == [
        '192.0.2.0/24',
        '198.51.100.0/24',
    ]
