"""GTSM (RFC 5082) needs two settings on every session socket, and each knob sets one.

`incoming-ttl` is the minimum TTL accepted from the peer, `outgoing-ttl` the TTL we send
with.  Before this, neither knob did its job in both directions:

- A session we opened got only `outgoing-ttl`.  `incoming-ttl` was never installed on it,
  so the inbound check was missing for every session this side initiated.
- A session the peer opened never got `outgoing-ttl`.  Instead `min_ttl` set `IP_TTL` on
  the shared listening socket to the incoming minimum, and accepted sockets inherited it.
  RFC 5082 section 3 has a GTSM sender use 255, not the minimum it accepts.

Now `min_ttl` sets the minimum only, both directions install both settings, and with
`incoming-ttl` alone we send 255, which is what the old code sent for the usual
`incoming-ttl 255` and what the RFC asks for in every other case.
"""

from __future__ import annotations

import socket
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.protocol.family import AFI
from exabgp.reactor import listener
from exabgp.reactor.network import outgoing, tcp
from exabgp.reactor.network.error import TTLError

PEER = '192.0.2.1'


class FakeSocket:
    """Records every setsockopt."""

    def __init__(self, refuse: bool = False) -> None:
        self.options: list[tuple[int, int, int]] = []
        self._refuse = refuse

    def setsockopt(self, level: int, option: int, value: int) -> None:
        if self._refuse:
            raise OSError(22, 'Invalid argument')
        self.options.append((level, option, value))

    def close(self) -> None:
        """Outgoing._setup closes the socket on any failure, so a failure must not mask itself."""


@pytest.fixture
def linux_minttl(monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(socket, 'IP_MINTTL', 21, raising=False)
    return 21


def test_min_ttl_does_not_set_the_ttl_we_send_with(linux_minttl: int) -> None:
    """The minimum accepted is not the TTL to send, and must not overwrite it."""
    io: Any = FakeSocket()

    tcp.min_ttl(io, PEER, 254)

    assert (socket.IPPROTO_IP, linux_minttl, 254) in io.options
    assert not [option for option in io.options if option[1] == socket.IP_TTL], io.options


def test_min_ttlv6_sets_the_minimum_hop_count_and_nothing_else() -> None:
    """The IPv6 listener needs its own minimum: IP_MINTTL on an AF_INET6 socket is not it."""
    io: Any = FakeSocket()

    tcp.min_ttlv6(io, PEER, 254)

    assert (socket.IPPROTO_IPV6, tcp.IPV6_MINHOPCOUNT, 254) in io.options
    assert not [option for option in io.options if option[1] == socket.IPV6_UNICAST_HOPS], io.options


@pytest.mark.parametrize(
    'outgoing_ttl, incoming_ttl, expected',
    [
        (None, None, None),  # no GTSM, the kernel default stays
        (10, None, 10),  # multihop, explicitly
        (None, 254, tcp.GTSM_SENDING_TTL),  # GTSM configured on one side only
        (200, 254, 200),  # an explicit outgoing-ttl wins
    ],
)
def test_sending_ttl(outgoing_ttl: int | None, incoming_ttl: int | None, expected: int | None) -> None:
    assert tcp.sending_ttl(outgoing_ttl, incoming_ttl) == expected


def setup_outgoing(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> FakeSocket:
    """Run Outgoing._setup against a fake socket, with nothing but the TTL code real."""
    io = FakeSocket()
    monkeypatch.setattr(outgoing, 'create', lambda afi, interface: io)
    monkeypatch.setattr(outgoing, 'md5', lambda *args: None)
    monkeypatch.setattr(outgoing, 'asynchronous', lambda *args: None)
    connection = outgoing.Outgoing(AFI.ipv4, PEER, '', **kwargs)
    assert connection._setup() is None
    # Connection.__del__ closes, and closing logs, and no logger is configured in a unit
    # test, so the collector would raise into pytest long after the assertions are done
    connection.io = None
    return io


def test_a_session_we_open_installs_the_incoming_minimum(monkeypatch: pytest.MonkeyPatch, linux_minttl: int) -> None:
    io = setup_outgoing(monkeypatch, incoming_ttl=254)

    assert (socket.IPPROTO_IP, linux_minttl, 254) in io.options, 'incoming-ttl was ignored on an outgoing session'
    assert (socket.IPPROTO_IP, socket.IP_TTL, tcp.GTSM_SENDING_TTL) in io.options, io.options


def test_a_session_we_open_still_sends_with_outgoing_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    io = setup_outgoing(monkeypatch, ttl=10)

    assert io.options == [(socket.IPPROTO_IP, socket.IP_TTL, 10)]


def accepted(io: FakeSocket, afi: AFI = AFI.ipv4) -> Mock:
    connection = Mock(io=io, afi=afi, peer=PEER)
    connection.name.return_value = f'incoming {PEER}'
    return connection


def neighbor(outgoing_ttl: int | None, incoming_ttl: int | None) -> dict[str, int | None]:
    return {'outgoing-ttl': outgoing_ttl, 'incoming-ttl': incoming_ttl}


def test_a_session_the_peer_opens_sends_with_outgoing_ttl() -> None:
    io = FakeSocket()

    listener.set_accepted_ttl(accepted(io), neighbor(10, None))

    assert io.options == [(socket.IPPROTO_IP, socket.IP_TTL, 10)], 'outgoing-ttl was ignored on an incoming session'


def test_a_session_the_peer_opens_sends_255_under_gtsm() -> None:
    io = FakeSocket()

    listener.set_accepted_ttl(accepted(io, AFI.ipv6), neighbor(None, 254))

    assert io.options == [(socket.IPPROTO_IPV6, socket.IPV6_UNICAST_HOPS, tcp.GTSM_SENDING_TTL)]


def test_an_accepted_session_without_ttl_settings_is_left_alone() -> None:
    io = FakeSocket()

    listener.set_accepted_ttl(accepted(io), neighbor(None, None))

    assert not io.options


def test_a_refused_ttl_on_an_accepted_session_is_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    """The peer will drop the session under GTSM; the log is where the reason is."""
    logged: list[str] = []
    monkeypatch.setattr(listener.log, 'error', lambda message, source: logged.append(str(message())))

    listener.set_accepted_ttl(accepted(FakeSocket(refuse=True)), neighbor(10, None))

    assert logged and 'ttl 10' in logged[0], logged


def test_the_error_type_is_what_set_accepted_ttl_catches() -> None:
    """set_accepted_ttl catches NetworkError, so a refusal has to be one."""
    io: Any = FakeSocket(refuse=True)
    with pytest.raises(TTLError):
        tcp.ttl(io, PEER, 10)
