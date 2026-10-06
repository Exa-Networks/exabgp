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

from exabgp.configuration.configuration import Configuration
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
