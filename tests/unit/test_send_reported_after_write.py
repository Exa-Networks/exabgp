"""A message is reported to the API after it has been written, not before.

A process which waits on a send-update to know a route has left needs the
report to mean the bytes were given to the socket. Reporting first also
claimed a message had been sent when the write went on to raise.

The session is real: a Protocol for a Peer of a Reactor, writing an UPDATE on a TCP
connection over the loopback, and reporting it to a helper whose stdin is a pipe. The
report is the helper's line being written, and when it is, the UPDATE has to be on the
wire already, which the other end of the connection can see without reading it.
"""

from __future__ import annotations

import asyncio
import os
import socket
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest

from exabgp.bgp.message.update import Update
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI
from exabgp.reactor.api.processes import Processes
from exabgp.reactor.loop import Reactor
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.network.incoming import Incoming
from exabgp.reactor.peer import Peer
from exabgp.reactor.protocol import Protocol
from tests import negotiation

HELPER = 'helper'
# an IPv4 unicast End-of-RIB: no withdrawn routes, no attributes
EOR_BODY = b'\x00\x00\x00\x00'
UPDATE_SIZE = 19 + len(EOR_BODY)


class PipedHelper:
    """The Popen of a helper process, as far as writing to it goes: its stdin is a pipe."""

    def __init__(self) -> None:
        self._reader, writer = os.pipe()
        os.set_blocking(self._reader, False)
        self.stdin = os.fdopen(writer, 'wb')

    def lines(self) -> list[str]:
        try:
            return os.read(self._reader, 65536).decode('ascii').splitlines()
        except BlockingIOError:
            return []

    def close(self) -> None:
        os.close(self._reader)
        self.stdin.close()


@pytest.fixture
def tcp() -> Iterator[tuple[socket.socket, socket.socket]]:
    """Both ends of an established TCP connection over the loopback: ours, and the peer's."""
    with socket.create_server(('127.0.0.1', 0)) as server:
        theirs = socket.create_connection(server.getsockname())
        ours, _ = server.accept()
    yield ours, theirs
    ours.close()
    theirs.close()


@pytest.fixture
def helper() -> Iterator[PipedHelper]:
    piped = PipedHelper()
    yield piped
    piped.close()


def _protocol(ours: socket.socket, helper: PipedHelper) -> Protocol:
    """A Protocol on `ours`, whose neighbor reports every UPDATE sent to `helper`."""
    reactor = Reactor(Configuration([''], text=True))
    reactor.processes = Processes()
    reactor.processes._process[HELPER] = helper  # type: ignore[assignment]
    reactor.processes._select_encoder(HELPER, {'encoder': 'json'})

    neighbor = negotiation.neighbor()
    neighbor.api = {'send-update': [HELPER], 'send-parsed': [HELPER], 'send-packets': [], 'send-consolidate': []}
    protocol = Protocol(Peer(neighbor, reactor))
    protocol.connection = Incoming(AFI.ipv4, '127.0.0.1', '127.0.0.1', ours)
    return protocol


def _update() -> Update:
    update = Update(EOR_BODY)
    update.parse(negotiation.negotiated())
    return update


def _on_the_wire(theirs: socket.socket) -> int:
    """How many bytes the peer has been sent and not yet read."""
    try:
        return len(theirs.recv(UPDATE_SIZE, socket.MSG_PEEK | socket.MSG_DONTWAIT))
    except BlockingIOError:
        return 0


def test_report_follows_the_write(tcp: Any, helper: PipedHelper) -> None:
    ours, theirs = tcp
    protocol = _protocol(ours, helper)
    seen_when_reported: list[int] = []
    write = os.write

    def reporting(fd: int, data: Any) -> int:
        seen_when_reported.append(_on_the_wire(theirs))
        return write(fd, data)

    with patch('exabgp.reactor.api.processes.os.write', side_effect=reporting):
        asyncio.run(protocol.write(_update(), negotiation.negotiated()))

    assert seen_when_reported == [UPDATE_SIZE], 'the UPDATE was reported before it was on the wire'
    assert len(helper.lines()) == 1


def test_a_failed_write_is_not_reported_as_sent(tcp: Any, helper: PipedHelper) -> None:
    ours, _ = tcp
    protocol = _protocol(ours, helper)
    # nothing more can be sent on this socket: the write raises EPIPE
    ours.shutdown(socket.SHUT_WR)

    with pytest.raises(NetworkError):
        asyncio.run(protocol.write(_update(), negotiation.negotiated()))

    assert helper.lines() == []
