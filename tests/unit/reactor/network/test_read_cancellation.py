"""A read cancelled by the main loop's deadline lost the bytes it had already taken.

Peer._main_loop reads each message under a 100ms deadline and, when it expires, keeps the
connection and loops round to read again:

    message = await asyncio.wait_for(self.proto.read_message(), timeout=0.1)

asyncio.wait_for cancels the coroutine it is waiting on.  Connection._reader_async holds
its buffer and its offset in coroutine locals, and sock_recv_into has already taken those
bytes out of the kernel socket buffer, where they cannot be read again.  CancelledError
unwinds the frame and they go with it, with nothing on the Connection recording that a
message was half read.  reader_async has the same gap one level up, between the nineteen
byte header read and the body read.

The next iteration then reads the tail of the previous message as though it were a fresh
header, the marker check fails, and the session is torn down with

    NotifyError(1, 1, 'The packet received does not contain a BGP marker')

which is not what happened.  Any message whose bytes span more than 100ms reaches this: one
dropped segment gives Linux a retransmit timeout of roughly 200ms, which is enough on its
own, and a table dump or a slow path widens it further.

This is a regression from the asyncio migration.  The generator reader kept alongside it is
resumable for free, because generator locals survive between next() calls.

See plan/plan-read-cancellation-desync.md.
"""

from __future__ import annotations

import asyncio
import os
import socket

import pytest

os.environ['exabgp_log_enable'] = 'false'

from exabgp.bgp.message import Message
from exabgp.protocol.family import AFI
from exabgp.reactor.network.connection import Connection

# The deadline Peer._main_loop uses.  The tests deliberately use the real number rather
# than a faster one: a fix which only works for a longer deadline has not fixed anything.
READ_TIMEOUT_SECONDS = 0.1
# Comfortably past it, so the split is not a race on a loaded machine.
DELIVERY_DELAY_SECONDS = 0.25

KEEPALIVE = Message.MARKER + Message.HEADER_LEN.to_bytes(2, 'big') + bytes([4])
KEEPALIVE_TYPE = 4


class LoopbackConnection(Connection):
    """A Connection over a socketpair, with the constructor's DNS and binding skipped.

    Connection.__init__ is called so the read state it sets up is the real one: a test
    which hand-rolled those fields would be testing its own fixture.
    """

    def __init__(self, sock: socket.socket) -> None:
        super().__init__(AFI.ipv4, '127.0.0.1', '127.0.0.1')
        self.io = sock
        self.established = True
        self.msg_size = 4096

    def name(self) -> str:
        return 'test'

    def session(self) -> str:
        return 'test'

    # close() is deliberately NOT overridden: the tests below assert what closing does to
    # the retained read state, and a stub would have them assert against the fixture.


@pytest.fixture
def pair() -> object:
    ours, theirs = socket.socketpair()
    ours.setblocking(False)
    theirs.setblocking(False)
    yield LoopbackConnection(ours), theirs
    ours.close()
    theirs.close()


async def read_once(connection: Connection) -> object:
    """One iteration of the main loop's read, deadline and all."""
    return await asyncio.wait_for(connection.reader_async(), timeout=READ_TIMEOUT_SECONDS)


def test_a_message_split_across_the_deadline_is_not_lost(pair: object) -> None:
    """The message arrives late, so the next read must return it, not a marker error.

    Ten bytes then the rest: the read is cancelled having already consumed the ten.
    """
    connection, peer = pair

    async def scenario() -> object:
        peer.send(KEEPALIVE[:10])

        async def deliver_the_rest() -> None:
            await asyncio.sleep(DELIVERY_DELAY_SECONDS)
            peer.send(KEEPALIVE[10:])

        asyncio.ensure_future(deliver_the_rest())

        with pytest.raises(asyncio.TimeoutError):
            await read_once(connection)

        # the loop keeps the connection and reads again, which is the whole point
        return await asyncio.wait_for(connection.reader_async(), timeout=1.0)

    _length, msg, _header, _body, error = asyncio.run(scenario())

    assert error is None, f'the split message desynchronised the stream: {error}'
    assert msg == KEEPALIVE_TYPE, 'the message which arrived late was not the one read back'


def test_a_message_split_at_the_header_boundary_is_not_lost(pair: object) -> None:
    """The header/body seam in reader_async, which _reader_async alone does not cover.

    Exactly the nineteen header bytes arrive, then the body after the deadline.  Neither
    _reader_async call is interrupted part way through its own buffer, so a fix which only
    makes _reader_async resumable still loses the header here.
    """
    connection, peer = pair
    # a KEEPALIVE has no body, so use a message which does: an UPDATE with empty content
    update_body = (0).to_bytes(2, 'big') + (0).to_bytes(2, 'big')
    update = Message.MARKER + (Message.HEADER_LEN + len(update_body)).to_bytes(2, 'big') + bytes([2]) + update_body

    async def scenario() -> object:
        peer.send(update[: Message.HEADER_LEN])

        async def deliver_the_body() -> None:
            await asyncio.sleep(DELIVERY_DELAY_SECONDS)
            peer.send(update[Message.HEADER_LEN :])

        asyncio.ensure_future(deliver_the_body())

        with pytest.raises(asyncio.TimeoutError):
            await read_once(connection)

        return await asyncio.wait_for(connection.reader_async(), timeout=1.0)

    length, msg, _header, _body, error = asyncio.run(scenario())

    assert error is None, f'the header was lost across the deadline: {error}'
    assert msg == 2, 'the body arrived but the message read back was not the UPDATE'
    assert length == Message.HEADER_LEN + len(update_body)


def test_a_second_message_behind_the_split_one_still_reads(pair: object) -> None:
    """Nothing is left in the buffer out of step.

    A stream which recovers the first message but drops or mis-frames what is queued behind
    it satisfies the first test and is still broken.
    """
    connection, peer = pair

    async def scenario() -> list:
        peer.send(KEEPALIVE[:10])

        async def deliver() -> None:
            await asyncio.sleep(DELIVERY_DELAY_SECONDS)
            peer.send(KEEPALIVE[10:])
            peer.send(KEEPALIVE)

        asyncio.ensure_future(deliver())

        with pytest.raises(asyncio.TimeoutError):
            await read_once(connection)

        first = await asyncio.wait_for(connection.reader_async(), timeout=1.0)
        second = await asyncio.wait_for(connection.reader_async(), timeout=1.0)
        return [first, second]

    first, second = asyncio.run(scenario())

    assert first[4] is None, f'first message desynchronised: {first[4]}'
    assert second[4] is None, f'the message queued behind it desynchronised: {second[4]}'
    assert first[1] == KEEPALIVE_TYPE and second[1] == KEEPALIVE_TYPE


def test_the_deadline_still_expires_when_no_data_arrives(pair: object) -> None:
    """The negative space: a fix which simply blocks until data arrives passes the rest.

    The main loop has keepalive timers, outbound updates and API work to do on every pass,
    so the read must still give the loop control back when the peer is quiet.
    """
    connection, _peer = pair

    async def scenario() -> None:
        started_at = asyncio.get_event_loop().time()
        with pytest.raises(asyncio.TimeoutError):
            await read_once(connection)
        return asyncio.get_event_loop().time() - started_at

    elapsed_seconds = asyncio.run(scenario())

    assert elapsed_seconds < READ_TIMEOUT_SECONDS * 5, 'the read did not return control to the loop'


def test_a_whole_message_delivered_promptly_still_reads(pair: object) -> None:
    """The other half of the negative space: the ordinary case is untouched."""
    connection, peer = pair

    async def scenario() -> object:
        peer.send(KEEPALIVE)
        return await read_once(connection)

    _length, msg, _header, _body, error = asyncio.run(scenario())

    assert error is None
    assert msg == KEEPALIVE_TYPE


# --- the forgetting half of the fix ----------------------------------------------------
#
# Resuming is only safe because closing forgets. Without these the clearing path is in the
# "it was never run" category that TIGER_STYLE section 5 warns about, and a fix which
# resumed onto a previous session's bytes would pass every test above.


def test_closing_forgets_a_partial_body(pair: object) -> None:
    """A half read message must not outlive the connection it was being read on."""
    connection, peer = pair

    async def scenario() -> None:
        peer.send(KEEPALIVE[:10])
        with pytest.raises(asyncio.TimeoutError):
            await read_once(connection)

    asyncio.run(scenario())
    assert connection._read_buffer is not None, 'the partial read was not retained in the first place'

    connection.close()

    assert connection._read_buffer is None, 'a closed connection kept its half read message'
    assert connection._read_offset_bytes == 0
    assert connection._read_header is None


def test_closing_forgets_a_read_header(pair: object) -> None:
    """The header is kept between two reads, so it needs forgetting as much as the buffer."""
    connection, peer = pair
    update_body = (0).to_bytes(2, 'big') + (0).to_bytes(2, 'big')
    update = Message.MARKER + (Message.HEADER_LEN + len(update_body)).to_bytes(2, 'big') + bytes([2]) + update_body

    async def scenario() -> None:
        peer.send(update[: Message.HEADER_LEN])
        with pytest.raises(asyncio.TimeoutError):
            await read_once(connection)

    asyncio.run(scenario())
    assert connection._read_header is not None, 'the header was not retained in the first place'

    connection.close()

    assert connection._read_header is None, 'a closed connection kept the header it had read'
    assert connection._read_length_bytes == 0
    assert connection._read_message_type == 0


def test_closing_forgets_even_when_the_socket_is_already_gone(pair: object) -> None:
    """close() is called on a connection with no io, and must still forget.

    _reader_async does exactly this on a closed connection. If clearing sat behind the
    `if not self.io` guard, whether the state survived would depend on which call to close()
    happened to come first.
    """
    connection, peer = pair

    async def scenario() -> None:
        peer.send(KEEPALIVE[:10])
        with pytest.raises(asyncio.TimeoutError):
            await read_once(connection)

    asyncio.run(scenario())
    connection.io = None  # the socket has gone away without close() having run

    connection.close()

    assert connection._read_buffer is None, 'the half read message survived a close with no socket'


# --- the seam inside one recv -----------------------------------------------------------
#
# The timing tests above split the message BETWEEN two sock_recv_into calls.  There is a
# narrower window inside a single call: the selector callback has already moved the bytes
# out of the kernel and set the future's result when the deadline cancels the task in the
# same event-loop batch.  Task.cancel() finds the future done, marks the task to cancel
# anyway, and CancelledError is raised at the await with the byte count ready and unread.
# Wall-clock timing cannot force that interleaving reliably; driving the future by hand
# forces it every run.


def test_bytes_consumed_in_the_same_tick_as_the_cancellation_are_kept(pair: object) -> None:
    """Completion and cancellation in one event-loop batch must not lose the bytes."""
    connection, peer = pair
    ten_bytes = KEEPALIVE[:10]

    async def scenario() -> bytes:
        loop = asyncio.get_running_loop()
        handed: dict = {}

        def stub_recv_into(sock: object, view: object) -> object:
            handed['view'] = view
            handed['future'] = loop.create_future()
            return handed['future']

        setattr(loop, 'sock_recv_into', stub_recv_into)
        try:
            task = asyncio.ensure_future(connection._reader_async(Message.HEADER_LEN))
            for _ in range(100):
                if 'future' in handed:
                    break
                await asyncio.sleep(0)
            else:
                raise AssertionError('the read never reached sock_recv_into')

            # the selector callback has consumed the bytes and set the result...
            handed['view'][: len(ten_bytes)] = ten_bytes
            handed['future'].set_result(len(ten_bytes))
            # ...and the deadline cancels the task before it runs again: the same batch
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            delattr(loop, 'sock_recv_into')

        assert connection._read_offset_bytes == len(ten_bytes), 'the consumed bytes were not recorded'

        # the rest arrives for real; the resumed read must return the header intact
        peer.send(KEEPALIVE[10:])
        view = await asyncio.wait_for(connection._reader_async(Message.HEADER_LEN), timeout=1.0)
        return bytes(view)

    header = asyncio.run(scenario())
    assert header == KEEPALIVE, 'the resumed read overwrote the bytes taken before the cancellation'


def test_a_recv_cancelled_while_still_pending_is_cancelled_cleanly(pair: object) -> None:
    """The other side of the seam: no bytes arrived, so nothing must be recorded.

    A recovery which blindly read the future's result would raise or record garbage here.
    """
    connection, peer = pair

    async def scenario() -> None:
        task = asyncio.ensure_future(connection._reader_async(Message.HEADER_LEN))
        for _ in range(100):
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert connection._read_offset_bytes == 0, 'a recv which never completed recorded progress'
