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
from typing import Any, cast
from unittest.mock import patch

import pytest

from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI
from exabgp.reactor import listener
from exabgp.reactor.network import outgoing, tcp
from exabgp.reactor.network.error import TTLError
from exabgp.reactor.network.incoming import Incoming
from tests import negotiation

PEER = '192.0.2.1'


class FakeSocket:
    """Records every setsockopt, and is enough of a socket for an Incoming to be built on."""

    def __init__(self, refuse: bool = False) -> None:
        self.options: list[tuple[int, int, int]] = []
        self.refuse = refuse

    def setsockopt(self, level: int, option: int, value: int) -> None:
        if self.refuse:
            raise OSError(22, 'Invalid argument')
        self.options.append((level, option, value))

    def setblocking(self, flag: bool) -> None:
        pass

    def close(self) -> None:
        pass


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


def test_min_ttlv6_does_not_set_the_hop_limit_we_send_with() -> None:
    io: Any = FakeSocket()

    tcp.min_ttlv6(io, PEER, 254)

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


# the levels the TTL options live at: what the socket is given at the others (address
# reuse, an MD5 key cleared on Linux) is not what these tests are about
TTL_LEVELS = (socket.IPPROTO_IP, socket.IPPROTO_IPV6)


def setup_outgoing(**kwargs: Any) -> list[tuple[int, int, int]]:
    """Run Outgoing._setup on a real socket, returning the TTL options it set.

    Outgoing is compiled, and the tcp functions it calls can not be replaced, so the socket
    is a real one and only setsockopt is recorded instead of performed: a function, not a
    Mock, so it is told which socket it is on.
    """
    options: list[tuple[int, int, int]] = []

    def setsockopt(sock: socket.socket, level: int, option: int, value: int | bytes) -> None:
        if level in TTL_LEVELS:
            assert isinstance(value, int), 'a TTL is set as a number'
            options.append((level, option, value))

    connection = outgoing.Outgoing(AFI.ipv4, PEER, '', **kwargs)
    with patch.object(socket.socket, 'setsockopt', setsockopt):
        assert connection._setup() is None
    connection.close()
    return options


def test_a_session_we_open_installs_the_incoming_minimum(linux_minttl: int) -> None:
    options = setup_outgoing(incoming_ttl=254)

    assert (socket.IPPROTO_IP, linux_minttl, 254) in options, 'incoming-ttl was ignored on an outgoing session'
    assert (socket.IPPROTO_IP, socket.IP_TTL, tcp.GTSM_SENDING_TTL) in options, options


def test_a_session_we_open_still_sends_with_outgoing_ttl() -> None:
    options = setup_outgoing(ttl=10)

    assert options == [(socket.IPPROTO_IP, socket.IP_TTL, 10)]


def accepted(io: FakeSocket, afi: AFI = AFI.ipv4, refuse: bool = False) -> Incoming:
    """A real Incoming over the fake socket, as the listener builds for a session the peer opened."""
    connection = Incoming(afi, PEER, '192.0.2.2', cast(socket.socket, io))
    # what the Incoming set up on it (TCP_NODELAY) is not what is under test
    io.options.clear()
    io.refuse = refuse
    return connection


def neighbor(outgoing_ttl: int | None, incoming_ttl: int | None) -> Neighbor:
    configured = negotiation.neighbor()
    configured.session.outgoing_ttl = outgoing_ttl
    configured.session.incoming_ttl = incoming_ttl
    return configured


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

    listener.set_accepted_ttl(accepted(FakeSocket(), refuse=True), neighbor(10, None))

    assert logged and 'ttl=10' in logged[0], logged


def test_the_error_type_is_what_set_accepted_ttl_catches() -> None:
    """set_accepted_ttl catches NetworkError, so a refusal has to be one."""
    io: Any = FakeSocket(refuse=True)
    with pytest.raises(TTLError):
        tcp.ttl(io, PEER, 10)
