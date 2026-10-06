"""A connection the configured peer refuses is sent the NOTIFICATION the peer chose.

Peer.handle_connection answers a connection it will not take with the writer of a
NOTIFICATION: (6, 3) when the neighbor was removed, (6, 5) when it is disabled, (6, 7) when
a session is already established. The listener read that answer only as "refused", logged
it and dropped the writer, so nothing was ever sent: the far end saw the socket close when
it was garbage collected, with no reason.
"""

from __future__ import annotations

import socket
from pathlib import Path

from exabgp.bgp.message import Message
from exabgp.bgp.message.notification import Notify
from exabgp.configuration.configuration import Configuration
from exabgp.reactor.listener import Listener
from exabgp.reactor.loop import Reactor
from exabgp.reactor.peer import Peer

CEASE = 6
PEER_DECONFIGURED = 3
CONNECTION_REJECTED = 5
NOTIFICATION = 3
# bounded: writing one NOTIFICATION to a local socket takes a handful of steps
MAX_WRITER_STEPS = 1000

CONFIGURED = """
neighbor 127.0.0.1 {
    router-id 1.1.1.1;
    local-address 127.0.0.1;
    local-as 65000;
    peer-as 65001;
    passive;
}
"""


def refused_with(tmp_path: Path, refuse: str) -> tuple[int, int]:
    """Configure one peer, make it refuse, connect to it, and read what the far end is sent."""
    configuration_file = tmp_path / 'configured.conf'
    configuration_file.write_text(CONFIGURED)
    configuration = Configuration([str(configuration_file)])
    assert configuration.reload(), configuration.error

    reactor = Reactor(None)
    (key, neighbor), *rest = configuration.neighbors.items()
    assert not rest, 'the configuration has one neighbor'
    peer = Peer(neighbor, reactor)
    reactor.register_peer(key, peer)
    if refuse == 'stopped':
        peer.stop()
    else:
        peer.disable(Notify(CEASE, 2))

    listener = Listener(reactor)
    listener.serving = True
    with socket.create_server(('127.0.0.1', 0)) as listening:
        far_end = socket.create_connection(listening.getsockname())
        accepted, _ = listening.accept()
        try:
            listener._accepted[listening] = accepted
            for _ in listener.new_connections():
                pass

            # the refusal is scheduled on the reactor, run it as the reactor would
            scheduled = [callback for _, callback in reactor.asynchronous._async]
            assert len(scheduled) == 1, scheduled
            for step, _ in enumerate(scheduled[0]):
                assert step < MAX_WRITER_STEPS, 'the NOTIFICATION was never written'

            far_end.settimeout(1.0)
            header = far_end.recv(Message.HEADER_LEN)
            length = int.from_bytes(header[16:18], 'big')
            body = far_end.recv(length - Message.HEADER_LEN)
        finally:
            far_end.close()
            accepted.close()

    assert header[18] == NOTIFICATION, header
    return body[0], body[1]


def test_a_removed_neighbor_sends_peer_deconfigured(tmp_path: Path) -> None:
    assert refused_with(tmp_path, 'stopped') == (CEASE, PEER_DECONFIGURED)


def test_a_disabled_neighbor_sends_connection_rejected(tmp_path: Path) -> None:
    assert refused_with(tmp_path, 'disabled') == (CEASE, CONNECTION_REJECTED)
