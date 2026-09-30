"""test_outgoing_authentication.py

An authentication key the kernel refuses is a permanent failure, not a transient
one.  Outgoing.establish_async() must say so once at error level and give up,
rather than burning max_attempts retries with the reason buried at debug level.

Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import errno
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

import pytest

from exabgp.protocol.family import AFI
from exabgp.reactor.network.outgoing import Outgoing

MD5 = {'md5': 'secret'}
TCP_AO = {'tcp_ao_keyid': 1, 'tcp_ao_algorithm': 'hmac-sha-256', 'tcp_ao_password': 'secret'}


def _outgoing(**authentication: Any) -> Outgoing:
    return Outgoing(AFI.ipv4, '192.0.2.1', '192.0.2.2', **authentication)


@contextmanager
def _attempts(platform: str, refused: OSError | None = None) -> Iterator[list[int]]:
    """Run on this platform, counting the sockets each connection attempt opens.

    Outgoing._setup is compiled, and a compiled method can not be replaced, so the failure
    is a real one: a platform with no MD5 and no TCP-AO refuses the key the way a kernel
    without them does, and refused makes the socket itself fail to open.
    """
    opened: list[int] = []
    real = socket.socket

    def opening(*args: Any) -> socket.socket:
        opened.append(len(opened))
        if refused is not None:
            raise refused
        return real(*args)

    with patch('platform.system', return_value=platform), patch.object(socket, 'socket', opening):
        yield opened


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'authentication, failure',
    [
        (MD5, 'ExaBGP has no MD5 support for Windows'),
        (TCP_AO, 'TCP-AO is only supported on Linux (current: Windows)'),
    ],
    ids=['md5', 'tcp-ao'],
)
async def test_establish_gives_up_on_a_refused_authentication_key(authentication: dict[str, Any], failure: str) -> None:
    connection = _outgoing(**authentication)

    with _attempts('Windows') as opened:
        with patch('exabgp.reactor.network.outgoing.log') as logger:
            connected = await connection.establish_async()

    assert not connected
    # one attempt only: retrying a key the kernel rejected can not succeed
    assert len(opened) == 1
    assert logger.error.call_count == 1
    assert logger.error.call_args[0][0]() == (
        f'connection.authentication.failed peer=192.0.2.1 port=179 error={failure}'
    )


@pytest.mark.asyncio
async def test_a_refused_key_is_reported_once_per_connection_attempt() -> None:
    """Giving up is per attempt, not per process.

    Peer.run() builds a fresh Outgoing and calls back after Delay.backoff(), so a
    permanent misconfiguration stays visible to an operator who attaches later
    instead of being announced once and never again.
    """
    connection = _outgoing(**MD5)

    with _attempts('Windows') as opened:
        with patch('exabgp.reactor.network.outgoing.log') as logger:
            for _ in range(3):
                assert not await connection.establish_async()

    # one attempt and one report per reconnection cycle, never a burst within one
    assert len(opened) == 3
    assert logger.error.call_count == 3


@pytest.mark.asyncio
async def test_establish_keeps_retrying_a_transient_setup_failure() -> None:
    connection = _outgoing(**MD5)

    # out of file descriptors: tcp.create reports NotConnected, which a retry may get past
    with _attempts('Windows', OSError(errno.EMFILE, 'Too many open files')) as opened:
        with patch('exabgp.reactor.network.outgoing.log') as logger:
            connected = await connection.establish_async(timeout=1.0, max_attempts=3)

    assert not connected
    assert len(opened) == 3
    assert logger.error.call_count == 0
