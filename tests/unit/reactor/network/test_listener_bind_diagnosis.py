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
import socket
from unittest.mock import MagicMock, patch

import pytest

from exabgp.protocol.ip import IP
from exabgp.reactor.listener import MAX_PRIVILEGED_PORT, Listener
from exabgp.reactor.loop import Reactor

LOCAL = IP.from_string('127.0.0.1')
PEER = IP.from_string('127.0.0.2')
BGP_PORT = 179


def _critical(log: MagicMock) -> list[str]:
    return [call[0][0]() for call in log.critical.call_args_list]


def _listener() -> Listener:
    # a real Reactor: the compiled Listener checks what it is given is one
    return Listener(Reactor(None))


def test_an_unusable_md5_key_is_not_reported_as_a_privilege_problem() -> None:
    listener = _listener()
    # the socket calls, not the functions calling them, are what can be replaced when the
    # listener is compiled: a Linux kernel built without TCP_MD5SIG refuses the option
    refused = OSError(errno.ENOPROTOOPT, 'Protocol not available')

    with patch('platform.system', return_value='Linux'), patch.object(socket.socket, 'setsockopt', side_effect=refused):
        with patch('exabgp.reactor.listener.log') as log:
            assert not listener.listen_on(LOCAL, PEER, BGP_PORT, 'secret', False)

    reported = _critical(log)
    assert any('TCP_MD5SIG' in line for line in reported), reported
    assert not any('root' in line for line in reported), reported


def test_a_privileged_port_says_so_and_names_the_port() -> None:
    listener = _listener()

    with patch.object(socket.socket, 'bind', side_effect=OSError(errno.EACCES, 'Permission denied')):
        with patch('exabgp.reactor.listener.log') as log:
            assert not listener.listen_on(LOCAL, PEER, BGP_PORT, None, False)

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
    listener = _listener()

    with patch.object(socket.socket, 'bind', side_effect=failure):
        with patch('exabgp.reactor.listener.log') as log:
            assert not listener.listen_on(LOCAL, PEER, BGP_PORT, None, False)

    reported = _critical(log)
    assert any(expected in line for line in reported), reported
