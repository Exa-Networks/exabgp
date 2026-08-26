"""test_listener_bind_diagnosis.py

listen_on() used to pick its hint from the effective uid and the port number
alone, so any failure on a privileged port as a normal user was reported as
"run as root" and the real reason was dropped.  An MD5 key the kernel cannot
install fails the same call and needs a different answer.

Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import errno
from unittest.mock import MagicMock, patch

import pytest

from exabgp.protocol.ip import IP
from exabgp.reactor.listener import MAX_PRIVILEGED_PORT, Listener
from exabgp.reactor.network.error import MD5Error

LOCAL = IP.from_string('127.0.0.1')
PEER = IP.from_string('127.0.0.2')
BGP_PORT = 179


def _critical(log: MagicMock) -> list[str]:
    return [call[0][0]() for call in log.critical.call_args_list]


def test_an_unusable_md5_key_is_not_reported_as_a_privilege_problem() -> None:
    listener = Listener(MagicMock())
    failure = MD5Error('This linux machine does not support TCP_MD5SIG, you can not use MD5')

    with patch('exabgp.reactor.listener.md5', side_effect=failure):
        with patch('exabgp.reactor.listener.log') as log:
            assert not listener.listen_on(LOCAL, PEER, BGP_PORT, 'secret', False, None)

    reported = _critical(log)
    assert any('TCP_MD5SIG' in line for line in reported), reported
    assert not any('root' in line for line in reported), reported


def test_a_privileged_port_says_so_and_names_the_port() -> None:
    listener = Listener(MagicMock())

    with patch.object(Listener, '_new_socket') as new_socket:
        new_socket.return_value.bind.side_effect = OSError(errno.EACCES, 'Permission denied')
        with patch('exabgp.reactor.listener.log') as log:
            assert not listener.listen_on(LOCAL, PEER, BGP_PORT, None, False, None)

    reported = _critical(log)
    assert any('requires root' in line for line in reported), reported
    assert any(str(MAX_PRIVILEGED_PORT) in line for line in reported), reported


@pytest.mark.parametrize(
    'failure, expected',
    [
        (OSError(errno.EADDRINUSE, 'Address already in use'), 'already be in use'),
        (OSError(errno.EADDRNOTAVAIL, 'Cannot assign requested address'), 'invalid address'),
    ],
    ids=['in-use', 'not-available'],
)
def test_every_bind_failure_reports_its_own_reason(failure: OSError, expected: str) -> None:
    listener = Listener(MagicMock())

    with patch.object(Listener, '_new_socket') as new_socket:
        new_socket.return_value.bind.side_effect = failure
        with patch('exabgp.reactor.listener.log') as log:
            assert not listener.listen_on(LOCAL, PEER, BGP_PORT, None, False, None)

    reported = _critical(log)
    assert any(expected in line for line in reported), reported
