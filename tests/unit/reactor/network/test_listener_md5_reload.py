"""test_listener_md5_reload.py

Listener._listen() reuses its listening socket across reloads, so the socket it
hands to tcp.md5() is not fresh.  Removing md5-password from the configuration
and reloading has to clear the key the kernel still holds, otherwise a passive
session with that peer keeps failing (#1388).

Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from contextlib import contextmanager
from struct import unpack
from unittest.mock import patch

from exabgp.protocol.ip import IP
from exabgp.reactor.listener import Listener
from exabgp.reactor.loop import Reactor

LOCAL = IP.from_string('127.0.0.1')
PEER = IP.from_string('127.0.0.2')

# linux/tcp.h, the option tcp.md5() installs the key with
TCP_MD5SIG = 14
# the option is a 128 byte __kernel_sockaddr_storage followed by tcp_md5sig
SOCKADDR_STORAGE_BYTES = 128


def _listener() -> Listener:
    # a real Reactor: the compiled Listener checks what it is given is one
    return Listener(Reactor(None))


# (socket, level, option, value) of each socket option set
OptionsSet = list[tuple[socket.socket, int, int, bytes]]


@contextmanager
def _kernel() -> Iterator[OptionsSet]:
    """Run as on Linux, recording every socket option set rather than setting it.

    The listener calls tcp.md5(), which the compiled build does not let a test replace, so
    what is recorded is what md5 asks the kernel for: the same thing, one step further in.
    A function, not a Mock, stands in for setsockopt, so it is told which socket it is on.
    """
    options: OptionsSet = []

    def setsockopt(sock: socket.socket, level: int, option: int, value: bytes) -> None:
        options.append((sock, level, option, value))

    with patch('platform.system', return_value='Linux'), patch.object(socket.socket, 'setsockopt', setsockopt):
        yield options


def _md5_keys(options: OptionsSet) -> list[tuple[socket.socket, bytes]]:
    """The socket and the key of each TCP_MD5SIG option set, in order."""
    keys = []
    for sock, level, option, value in options:
        if (level, option) != (socket.IPPROTO_TCP, TCP_MD5SIG):
            continue
        length, key = unpack('2xH4x80s', value[SOCKADDR_STORAGE_BYTES:])
        keys.append((sock, key[:length]))
    return keys


def test_reload_clearing_the_password_clears_the_key_on_the_reused_socket() -> None:
    listener = _listener()

    try:
        with _kernel() as options:
            # first pass binds a new socket and installs the key
            listener._listen(LOCAL, PEER, 0, 'secret', False, None)
            assert len(listener._sockets) == 1
            sock = next(iter(listener._sockets))
            assert _md5_keys(options) == [(sock, b'secret')]

            # a reload without md5-password must reuse that socket and clear the key
            options.clear()
            listener._listen(LOCAL, PEER, 0, None, False, None)

            assert len(listener._sockets) == 1, 'the listening socket must be reused'
            # a zero length key is what clears the entry
            assert _md5_keys(options) == [(sock, b'')]
    finally:
        listener.stop()


def test_reload_keeping_the_password_reinstalls_it_on_the_reused_socket() -> None:
    listener = _listener()

    try:
        with _kernel() as options:
            listener._listen(LOCAL, PEER, 0, 'secret', False, None)
            sock = next(iter(listener._sockets))

            options.clear()
            listener._listen(LOCAL, PEER, 0, 'secret', False, None)

            assert _md5_keys(options) == [(sock, b'secret')]
    finally:
        listener.stop()
