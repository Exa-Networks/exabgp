"""A message read the way the daemon reads one: a real connection, a real Protocol.

The header is not parsed by any message class: the marker, the Length field and the
per-type lengths are checked in `reactor/network/connection.py`, the type in
`reactor/protocol.py`.  A test calling a message decoder skips every one of those, so a
requirement about what a peer is answered is only proven through here.
"""

from __future__ import annotations

import asyncio
from struct import pack

from exabgp.bgp.message import Message, Open
from tests import negotiation

MARKER = bytes([0xFF] * 16)


def header(length: int, message_type: int) -> bytes:
    """A well formed header, for whatever the caller wants to be wrong about."""
    return MARKER + pack('!H', length) + bytes([int(message_type)])


def read_wire(wire: bytes, received_open: Open | None = None) -> Message | None:
    """Hand `wire` to a real connection and a real Protocol, and return what came back.

    There is no stand-in: the Peer and its Reactor are real, with no API process asking to
    hear of anything.  Everything which looks at the bytes is the production code.
    `received_open` is the OPEN the peer sent, for what depends on it.
    """

    async def run() -> Message | None:
        protocol, _ = negotiation.protocol()
        protocol.negotiated.received_open = received_open
        theirs = negotiation.connect(protocol)
        try:
            theirs.sendall(wire)
            return await protocol.read_message()
        finally:
            theirs.close()
            protocol.close()

    return asyncio.run(run())
