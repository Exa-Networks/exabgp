"""RFC 5082: the Generalized TTL Security Mechanism, as exabgp's ttl-security.

GTSM is two numbers on one socket and they are not the same number. `incoming-ttl` is the
minimum a packet must arrive with to be believed, installed as IP_MINTTL or
IPV6_MINHOPCOUNT. What we transmit with has to be 255 whatever that minimum is, so that
the far end can tell from the TTL how many hops the packet crossed.

Getting the two confused is the failure this file watches for, and it has happened here
before: see tests/unit/test_ttl_security_reports_what_it_cannot_do.py, which covers the
receive half and the platforms where the kernel has no option to install.

The ledger entries these prove are in qa/rfc/rfc5082.toml.
"""

from __future__ import annotations

import socket
from typing import Any, cast

import pytest

from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI
from exabgp.reactor import listener
from exabgp.reactor.network import tcp


# RFC 5082 section 3 wants 255 on the wire. 254 is the matching minimum for a directly
# connected neighbour: one hop crossed, one decrement.
GTSM_MINIMUM = 254
GTSM_SENT = 255

# linux/in.h. CPython exports neither, so the tests pin them the way tcp.py has to.
IP_MINTTL = 21


class FakeSocket:
    """Records every setsockopt instead of performing it."""

    def __init__(self) -> None:
        self.options: list[tuple[int, int, int]] = []

    def setsockopt(self, level: int, option: int, value: int) -> None:
        self.options.append((level, option, value))


@pytest.fixture
def linux_minttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """A platform whose kernel has the inbound option, so it is installed rather than warned about."""
    monkeypatch.setattr(socket, 'IP_MINTTL', IP_MINTTL, raising=False)


def install_sending_ttl(io: FakeSocket, afi: AFI, peer: str, value: int | None) -> None:
    """tcp.set_sending_ttl, with the one cast a recording socket needs to reach it."""
    tcp.set_sending_ttl(cast(socket.socket, io), afi, peer, value)


def install_minimum_ttl(io: FakeSocket, afi: AFI, peer: str, value: int | None) -> None:
    """tcp.set_minimum_ttl, likewise."""
    tcp.set_minimum_ttl(cast(socket.socket, io), afi, peer, value)


def neighbour(ttl: str = '') -> Neighbor:
    """A neighbour built by the real configuration parser."""
    text = f"""
neighbor 192.0.2.1 {{
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as 65001;
    peer-as 65002;
    {ttl}
    family {{ ipv4 unicast; }}
}}
"""
    configuration = Configuration([text], text=True)
    assert configuration.reload(), str(configuration.error)
    parsed: Neighbor = next(iter(configuration.neighbors.values()))
    return parsed


def accepted_connection(io: FakeSocket, afi: AFI) -> Any:
    """What reactor/listener.py hands set_accepted_ttl for a session the peer opened."""

    class Connection:
        def __init__(self) -> None:
            self.io = io
            self.afi = afi
            self.peer = '192.0.2.1'

        def name(self) -> str:
            return 'incoming-192.0.2.1'

    return Connection()


# ============================================================ what we transmit with


@pytest.mark.rfc('rfc5082#3-sending-ttl-is-255')
@pytest.mark.parametrize(
    'afi, level, option',
    [
        (AFI.ipv4, socket.IPPROTO_IP, socket.IP_TTL),
        (AFI.ipv6, socket.IPPROTO_IPV6, socket.IPV6_UNICAST_HOPS),
    ],
    ids=['ipv4', 'ipv6'],
)
def test_a_gtsm_session_transmits_with_the_maximum_ttl(afi: AFI, level: int, option: int) -> None:
    """The minimum we accept is not the TTL we send with, and 64 would never arrive.

    Setting the sending TTL to the minimum instead of 255 is the mistake this asserts
    against: the far end running GTSM would see a TTL below its own minimum and drop
    every packet, so the session would never come up.
    """
    neighbor = neighbour(f'incoming-ttl {GTSM_MINIMUM};')
    io = FakeSocket()

    value = tcp.sending_ttl(neighbor.session.outgoing_ttl, neighbor.session.incoming_ttl)
    install_sending_ttl(io, afi, '192.0.2.1', value)

    assert value == GTSM_SENT, f'a GTSM session was going to transmit with TTL {value}'
    assert (level, option, GTSM_SENT) in io.options, f'the sending TTL was never installed: {io.options}'


@pytest.mark.rfc('rfc5082#3-sending-ttl-is-255')
def test_a_session_the_peer_opened_also_transmits_with_the_maximum_ttl() -> None:
    """GTSM is symmetric, and a passive neighbour is the half that was once missed.

    The listening socket is shared by every neighbour on the address, so the sending TTL
    can only be set once the accepted connection has been matched to a configuration.
    """
    neighbor = neighbour(f'incoming-ttl {GTSM_MINIMUM};')
    io = FakeSocket()

    listener.set_accepted_ttl(accepted_connection(io, AFI.ipv4), neighbor)

    assert (socket.IPPROTO_IP, socket.IP_TTL, GTSM_SENT) in io.options, (
        f'an accepted GTSM session kept the kernel default TTL: {io.options}'
    )


@pytest.mark.rfc('rfc5082#3-sending-ttl-is-255', polarity='negative')
def test_a_session_without_gtsm_keeps_the_kernel_default() -> None:
    """The sentence is about GTSM-enabled sessions only. 255 on every session is a change
    of behaviour for every plain eBGP peering exabgp has, and not one the RFC asks for."""
    neighbor = neighbour()
    io = FakeSocket()

    value = tcp.sending_ttl(neighbor.session.outgoing_ttl, neighbor.session.incoming_ttl)
    install_sending_ttl(io, AFI.ipv4, '192.0.2.1', value)

    assert value is None, f'a neighbour with no ttl-security was given a sending TTL of {value}'
    assert not io.options, f'a socket option was set on a session which asked for none: {io.options}'


# ============================================================ what we accept


@pytest.mark.rfc('rfc5082#3-must-not-drop-trusted-or-unknown')
def test_the_minimum_installed_is_the_one_configured(linux_minttl: None) -> None:
    """A minimum above the configured one would drop Trusted packets.

    Nothing on this side classifies a packet: the kernel compares the arriving TTL with
    this number, so the number is the whole of exabgp's part in the MUST NOT.
    """
    neighbor = neighbour(f'incoming-ttl {GTSM_MINIMUM};')
    io = FakeSocket()

    install_minimum_ttl(io, AFI.ipv4, '192.0.2.1', neighbor.session.incoming_ttl)

    assert io.options == [(socket.IPPROTO_IP, IP_MINTTL, GTSM_MINIMUM)], (
        f'the kernel was given a minimum which is not the configured one: {io.options}'
    )


@pytest.mark.rfc('rfc5082#3-must-not-drop-trusted-or-unknown')
def test_the_ipv6_minimum_installed_is_the_one_configured() -> None:
    """IPV6_MINHOPCOUNT, which tcp.py pins at 73 because CPython does not export it."""
    neighbor = neighbour(f'incoming-ttl {GTSM_MINIMUM};')
    io = FakeSocket()

    install_minimum_ttl(io, AFI.ipv6, '2001:db8::1', neighbor.session.incoming_ttl)

    assert io.options == [(socket.IPPROTO_IPV6, 73, GTSM_MINIMUM)], (
        f'the kernel was given a hop limit minimum which is not the configured one: {io.options}'
    )


@pytest.mark.rfc('rfc5082#3-must-not-drop-trusted-or-unknown', polarity='negative')
@pytest.mark.parametrize('afi', [AFI.ipv4, AFI.ipv6], ids=['ipv4', 'ipv6'])
def test_a_session_without_gtsm_installs_no_minimum(linux_minttl: None, afi: AFI) -> None:
    """Packets on a session nobody registered are Unknown, and GTSM may not drop those."""
    neighbor = neighbour()
    io = FakeSocket()

    install_minimum_ttl(io, afi, '192.0.2.1', neighbor.session.incoming_ttl)

    assert not io.options, f'a minimum TTL was installed on a session which never asked for GTSM: {io.options}'


# ============================================================ off unless asked for


@pytest.mark.rfc('rfc5082#3-should-not-be-enabled-by-default')
def test_ttl_security_is_off_until_it_is_configured(linux_minttl: None) -> None:
    """A neighbour with no ttl statement must behave exactly as it did before GTSM existed."""
    neighbor = neighbour()

    assert neighbor.session.incoming_ttl is None, 'ttl-security defaulted to on'
    assert neighbor.session.outgoing_ttl is None, 'an outgoing TTL was invented'

    io = FakeSocket()
    install_minimum_ttl(io, AFI.ipv4, '192.0.2.1', neighbor.session.incoming_ttl)
    install_sending_ttl(io, AFI.ipv4, '192.0.2.1', tcp.sending_ttl(None, neighbor.session.incoming_ttl))

    assert not io.options, f'the default configuration touched the socket: {io.options}'


@pytest.mark.rfc('rfc5082#3-should-not-be-enabled-by-default', polarity='negative')
def test_ttl_security_is_on_once_it_is_configured(linux_minttl: None) -> None:
    """Off by default is only a defensible default if asking for it actually turns it on."""
    neighbor = neighbour(f'incoming-ttl {GTSM_MINIMUM};')
    io = FakeSocket()

    install_minimum_ttl(io, AFI.ipv4, '192.0.2.1', neighbor.session.incoming_ttl)

    assert neighbor.session.incoming_ttl == GTSM_MINIMUM
    assert io.options, 'ttl-security was configured and no socket option was installed'
