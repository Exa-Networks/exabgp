"""test_outgoing_authentication.py

An authentication key the kernel refuses is a permanent failure, not a transient
one.  Outgoing.establish_async() must say so once at error level and give up,
rather than burning max_attempts retries with the reason buried at debug level.

Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from exabgp.protocol.family import AFI
from exabgp.reactor.network.error import MD5Error, NotConnected, TCPAOError
from exabgp.reactor.network.outgoing import Outgoing


def _outgoing() -> Outgoing:
    return Outgoing(AFI.ipv4, '192.0.2.1', '192.0.2.2', md5='secret')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'failure',
    [
        MD5Error('This linux machine does not support TCP_MD5SIG, you can not use MD5'),
        TCPAOError('TCP-AO requires Linux 6.7 or later'),
    ],
    ids=['md5', 'tcp-ao'],
)
async def test_establish_gives_up_on_a_refused_authentication_key(failure: Exception) -> None:
    connection = _outgoing()

    with patch.object(Outgoing, '_setup', return_value=failure) as setup:
        with patch('exabgp.reactor.network.outgoing.log') as logger:
            connected = await connection.establish_async()

    assert not connected
    # one attempt only: retrying a key the kernel rejected can not succeed
    assert setup.call_count == 1
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
    connection = _outgoing()
    failure = MD5Error('This linux machine does not support TCP_MD5SIG, you can not use MD5')

    with patch.object(Outgoing, '_setup', return_value=failure) as setup:
        with patch('exabgp.reactor.network.outgoing.log') as logger:
            for _ in range(3):
                assert not await connection.establish_async()

    # one attempt and one report per reconnection cycle, never a burst within one
    assert setup.call_count == 3
    assert logger.error.call_count == 3


@pytest.mark.asyncio
async def test_establish_keeps_retrying_a_transient_setup_failure() -> None:
    connection = _outgoing()

    with patch.object(Outgoing, '_setup', return_value=NotConnected('Could not create socket')) as setup:
        with patch('exabgp.reactor.network.outgoing.log') as logger:
            connected = await connection.establish_async(timeout=1.0, max_attempts=3)

    assert not connected
    assert setup.call_count == 3
    assert logger.error.call_count == 0
