#!/usr/bin/env python3
# encoding: utf-8
"""test_listener_socket_options.py

SO_REUSEADDR and IPV6_V6ONLY shared one try in _listen, so a platform which refused the
first never had the second asked for at all.  The listening socket then accepted
IPv4-mapped connections although exabgp had asked it not to, and neither refusal was
logged, so the only symptom was a connection arriving on an address nobody expected.

They are two independent requests now, and each says what happened.
"""

import errno
import socket
from typing import Any
from unittest.mock import MagicMock, patch

from exabgp.reactor.listener import set_listener_options

REFUSED = OSError(errno.ENOPROTOOPT, 'Protocol not available')


def _requested(sock: MagicMock) -> set:
    """The (level, option) pairs which were actually asked of the socket."""
    return {(call[0][0], call[0][1]) for call in sock.setsockopt.call_args_list}


def _lines(recorded: Any) -> list:
    return [call[0][0]() for call in recorded.call_args_list]


def test_a_refused_reuseaddr_does_not_skip_v6only() -> None:
    """The bug: one try for both meant the first failure cancelled the second request."""
    sock = MagicMock()
    sock.setsockopt.side_effect = [REFUSED, None]

    with patch('exabgp.reactor.listener.log'):
        set_listener_options(sock, True)

    assert (socket.IPPROTO_IPV6, socket.IPV6_V6ONLY) in _requested(sock), _requested(sock)


def test_a_refused_reuseaddr_is_logged_and_is_not_fatal() -> None:
    sock = MagicMock()
    sock.setsockopt.side_effect = [REFUSED, None]

    with patch('exabgp.reactor.listener.log') as log:
        set_listener_options(sock, True)

    assert any('SO_REUSEADDR' in line for line in _lines(log.debug)), _lines(log.debug)


def test_a_refused_v6only_says_which_connections_may_now_arrive() -> None:
    sock = MagicMock()
    sock.setsockopt.side_effect = [None, REFUSED]

    with patch('exabgp.reactor.listener.log') as log:
        set_listener_options(sock, True)

    reported = _lines(log.warning)
    assert any('IPV6_V6ONLY' in line for line in reported), reported
    assert any('IPv4-mapped' in line for line in reported), reported


def test_an_ipv4_socket_is_never_asked_for_v6only() -> None:
    sock = MagicMock()

    with patch('exabgp.reactor.listener.log'):
        set_listener_options(sock, False)

    assert _requested(sock) == {(socket.SOL_SOCKET, socket.SO_REUSEADDR)}


def test_a_missing_constant_is_survived_as_well_as_a_refusal() -> None:
    """AttributeError was caught before and still is: an old Python without the constant."""
    sock = MagicMock()
    sock.setsockopt.side_effect = AttributeError('IPV6_V6ONLY')

    with patch('exabgp.reactor.listener.log'):
        set_listener_options(sock, True)
