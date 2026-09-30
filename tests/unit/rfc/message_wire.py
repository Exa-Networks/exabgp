"""A message read the way the daemon reads one: a real connection, a real Protocol.

The header is not parsed by any message class: the marker, the Length field and the
per-type lengths are checked in `reactor/network/connection.py`, the type in
`reactor/protocol.py`.  A test calling a message decoder skips every one of those, so a
requirement about what a peer is answered is only proven through here.
"""

from __future__ import annotations

import asyncio
import socket
from collections import defaultdict
from struct import pack
from unittest.mock import Mock

from exabgp.bgp.message import Message, Open
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI
from exabgp.reactor.network.outgoing import Outgoing
from exabgp.reactor.protocol import Protocol

MARKER = bytes([0xFF] * 16)

# read_message indexes these three rather than using .get, so a Neighbor built outside the
# configuration parser has to carry them before it can be read from.
API_KEYS = ('receive-packets', 'receive-consolidate', 'receive-parsed')


def header(length: int, message_type: int) -> bytes:
    """A well formed header, for whatever the caller wants to be wrong about."""
    return MARKER + pack('!H', length) + bytes([int(message_type)])


def read_wire(wire: bytes, received_open: Open | None = None) -> Message | None:
    """Hand `wire` to a real connection and a real Protocol, and return what came back.

    The only stand-in is the Peer, which read_message uses for its statistics counter and
    for the API fan-out we switch off above.  Everything which looks at the bytes is the
    production code.  `received_open` is the OPEN the peer sent, for what depends on it.
    """

    async def run() -> Message | None:
        neighbor = Neighbor()
        for key in API_KEYS:
            neighbor.api[key] = False
        peer = Mock()
        peer.neighbor = neighbor
        peer.stats = defaultdict(int)

        protocol = Protocol(peer)
        protocol.negotiated.received_open = received_open
        ours, theirs = socket.socketpair()
        ours.setblocking(False)
        connection = Outgoing(AFI.ipv4, 'peer', 'local')
        connection.io = ours
        protocol.connection = connection
        try:
            theirs.sendall(wire)
            return await protocol.read_message()
        finally:
            theirs.close()
            connection.close()

    return asyncio.run(run())
