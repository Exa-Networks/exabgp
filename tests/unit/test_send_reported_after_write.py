"""A message is reported to the API after it has been written, not before.

A process which waits on a send-update to know a route has left needs the
report to mean the bytes were given to the socket. Reporting first also
claimed a message had been sent when the write went on to raise.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from exabgp.reactor.protocol import Protocol
from exabgp.bgp.message import Message


class Recorder:
    """A connection which records the order of what happens to it."""

    def __init__(self, order: list[str], fail: bool = False):
        self.order = order
        self.fail = fail

    async def writer_async(self, raw: bytes) -> None:
        if self.fail:
            raise ConnectionResetError('peer went away')
        self.order.append('write')


def _protocol(order: list[str], fail: bool = False) -> Protocol:
    protocol = Protocol.__new__(Protocol)
    protocol.connection = Recorder(order, fail)
    protocol.neighbor = MagicMock()
    protocol.neighbor.api = {'send-update': True}
    protocol.peer = MagicMock()
    protocol.peer.stats = {'send-update': 0}
    protocol._to_api = lambda direction, message, raw: order.append('report')
    return protocol


def test_report_follows_the_write():
    order: list[str] = []
    message = MagicMock()
    message.ID = Message.CODE.UPDATE
    message.pack_message.return_value = b'\x00' * 19

    asyncio.run(_protocol(order).write(message, MagicMock()))

    assert order == ['write', 'report']


def test_a_failed_write_is_not_reported_as_sent():
    order: list[str] = []
    message = MagicMock()
    message.ID = Message.CODE.UPDATE
    message.pack_message.return_value = b'\x00' * 19

    with pytest.raises(ConnectionResetError):
        asyncio.run(_protocol(order, fail=True).write(message, MagicMock()))

    assert order == []
