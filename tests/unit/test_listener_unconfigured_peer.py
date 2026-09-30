"""A connection from a peer nobody configured is refused with Connection Rejected.

RFC 4486 section 4 gives this case as its example of (6, 5): a connection disallowed
"e.g., the peer is not configured locally".  The listener sent (6, 3) Peer De-configured,
which is for a peering the speaker had and decided to remove.
"""

from __future__ import annotations

import socket

import pytest

from exabgp.bgp.message import Message
from exabgp.reactor.listener import Listener
from exabgp.reactor.loop import Reactor

CEASE = 6
CONNECTION_REJECTED = 5
NOTIFICATION = 3

# bounded: writing one NOTIFICATION to a local socket takes a handful of steps
MAX_WRITER_STEPS = 1000


def refused_with() -> tuple[int, int]:
    """Accept a real connection with no neighbor configured, and read what the peer is sent.

    The listener is compiled, so neither its accepted socket nor the connection it builds
    can be replaced: the connection is a real one, from a real listening socket, and the
    answer is read off the wire by the far end.
    """
    reactor = Reactor(None)
    listener = Listener(reactor)
    listener.serving = True

    with socket.create_server(('127.0.0.1', 0)) as listening:
        peer = socket.create_connection(listening.getsockname())
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

            peer.settimeout(1.0)
            header = peer.recv(Message.HEADER_LEN)
            length = int.from_bytes(header[16:18], 'big')
            body = peer.recv(length - Message.HEADER_LEN)
        finally:
            peer.close()
            accepted.close()

    assert header[18] == NOTIFICATION, header
    return body[0], body[1]


@pytest.mark.rfc('rfc4486#4-connection-rejected')
def test_an_unconfigured_peer_is_sent_connection_rejected() -> None:
    assert refused_with() == (CEASE, CONNECTION_REJECTED)
