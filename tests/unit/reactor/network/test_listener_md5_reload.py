"""test_listener_md5_reload.py

Listener._listen() reuses its listening socket across reloads, so the socket it
hands to tcp.md5() is not fresh.  Removing md5-password from the configuration
and reloading has to clear the key the kernel still holds, otherwise a passive
session with that peer keeps failing (#1388).

Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from exabgp.protocol.ip import IP
from exabgp.reactor.listener import Listener

LOCAL = IP.from_string('127.0.0.1')
PEER = IP.from_string('127.0.0.2')


def _listener() -> Listener:
    return Listener(MagicMock())


def test_reload_clearing_the_password_clears_the_key_on_the_reused_socket() -> None:
    listener = _listener()

    try:
        with patch('exabgp.reactor.listener.md5') as md5:
            # first pass binds a new socket and installs the key
            listener._listen(LOCAL, PEER, 0, 'secret', False, None)
            assert len(listener._sockets) == 1
            sock = next(iter(listener._sockets))
            assert md5.call_args_list == [(((sock, PEER.top(), 0, 'secret', False)), {})]

            # a reload without md5-password must reuse that socket and clear the key
            md5.reset_mock()
            listener._listen(LOCAL, PEER, 0, None, False, None)

            assert len(listener._sockets) == 1, 'the listening socket must be reused'
            md5.assert_called_once_with(sock, PEER.top(), 0, '', False)
    finally:
        listener.stop()


def test_reload_keeping_the_password_reinstalls_it_on_the_reused_socket() -> None:
    listener = _listener()

    try:
        with patch('exabgp.reactor.listener.md5') as md5:
            listener._listen(LOCAL, PEER, 0, 'secret', False, None)
            sock = next(iter(listener._sockets))

            md5.reset_mock()
            listener._listen(LOCAL, PEER, 0, 'secret', False, None)

            md5.assert_called_once_with(sock, PEER.top(), 0, 'secret', False)
    finally:
        listener.stop()
