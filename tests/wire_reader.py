"""Drive Connection.reader_async over a real socket, for tests of the message framing.

The daemon reads every message through reader_async. A test which replaced the socket
reader with a stub would be testing the stub's idea of framing, so the bytes go through a
socketpair and the real _reader_async takes them off it.

The peer side writes from a thread: a message larger than the socket buffer would block a
write made before the read starts. When the reader stops early (a header error returns
before the body is read) the peer's write fails once our side closes, which is expected.
"""

from __future__ import annotations

import asyncio
import socket
import threading

from exabgp.protocol.family import AFI
from exabgp.reactor.network.connection import Connection
from exabgp.reactor.network.error import NotifyError
from exabgp.util.types import Buffer
from exabgp.bgp.message.message import MessageCode

ReadResult = tuple[int, MessageCode, Buffer, Buffer, NotifyError | None]

# RFC 4271 4.1: the largest message a session without Extended Message may carry.
STANDARD_MSG_SIZE_BYTES = 4096

# How long the peer thread may take to finish once our side is closed.
PEER_JOIN_SECONDS = 5.0


def loopback_connection(sock: socket.socket, msg_size: int = STANDARD_MSG_SIZE_BYTES) -> Connection:
    """A Connection reading from sock, with the constructor's own state left as it is."""
    sock.setblocking(False)
    connection = Connection(AFI.ipv4, '127.0.0.1', '127.0.0.1')
    connection.io = sock
    connection.established = True
    connection.msg_size = msg_size
    return connection


def _send_then_close(sock: socket.socket, data: bytes) -> None:
    try:
        sock.sendall(data)
        sock.shutdown(socket.SHUT_WR)
    except OSError:
        # Our side closed after refusing the header, before the body was all written.
        pass


def read_messages(data: bytes, count: int, msg_size: int = STANDARD_MSG_SIZE_BYTES) -> list[ReadResult]:
    """Send data from the peer, then call reader_async count times and return each result.

    The peer closes its side after data, so a read wanting more than was sent raises
    LostConnection, as it would against a peer which went away mid-message.
    """
    assert count > 0, 'a read of nothing tests nothing'
    ours, theirs = socket.socketpair()
    connection = loopback_connection(ours, msg_size)
    peer = threading.Thread(target=_send_then_close, args=(theirs, data), daemon=True)
    peer.start()

    async def read_all() -> list[ReadResult]:
        return [await connection.reader_async() for _ in range(count)]

    try:
        return asyncio.run(read_all())
    finally:
        connection.close()
        ours.close()
        peer.join(PEER_JOIN_SECONDS)
        theirs.close()


def read_message(data: bytes, msg_size: int = STANDARD_MSG_SIZE_BYTES) -> ReadResult:
    """Send data from the peer and return what one reader_async call makes of it."""
    return read_messages(data, 1, msg_size)[0]


def tcp_socketpair() -> tuple[socket.socket, socket.socket]:
    """The two ends of a TCP connection over loopback: (accepted, connecting).

    socket.socketpair() is AF_UNIX, where the kernel refuses TCP options such as
    TCP_NODELAY, so Incoming, which sets them on the socket it is given, fails on it.
    The compiled build does not let a test replace the tcp functions Incoming calls, so
    the test gets a socket those functions work on instead.
    """
    with socket.create_server(('127.0.0.1', 0)) as listener:
        connecting = socket.create_connection(listener.getsockname())
        accepted, _ = listener.accept()
    return accepted, connecting
