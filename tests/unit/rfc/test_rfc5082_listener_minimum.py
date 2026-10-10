"""RFC 5082 on a platform with IP_MINTTL but no saved SYN (FreeBSD).

The ledger these tests are joined to is qa/rfc/rfc5082.toml.

On Linux the listener keeps the headers of each SYN (TCP_SAVE_SYN), so the TTL of the
handshake is checked once the connection is matched to its neighbour, and the listening
socket carries no minimum: it is shared, and one minimum there would drop the Unknown
packets of a neighbour without GTSM. Where the SYN is not kept, the handshake and what
comes before the minimum reaches the accepted socket are checked only if the listening
socket carries the minimum. It does when every neighbour behind it asks for the same one,
which drops nothing that neighbour would not; otherwise it carries none, and says so.

The platform is mocked: these run everywhere, and the socket only records what is set.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from exabgp.bgp.neighbor import Neighbor
from exabgp.reactor import listener as listener_module
from exabgp.reactor.listener import Listener
from exabgp.reactor.network import tcp
from exabgp.reactor.network.incoming import Incoming
from tests import negotiation

FREEBSD_IP_MINTTL = 66
LOCAL = '127.0.0.1'


class RecordingSocket:
    """A listening socket which remembers the options set on it."""

    def __init__(self) -> None:
        self.options: dict[tuple[int, int], int] = {}

    def setsockopt(self, level: int, option: int, value: int) -> None:
        self.options[(level, option)] = value

    def setblocking(self, flag: bool) -> None:
        pass

    def close(self) -> None:
        pass

    def minimum(self) -> int | None:
        return self.options.get((tcp.socket.IPPROTO_IP, FREEBSD_IP_MINTTL))


def gtsm(peer_address: str, incoming_ttl: int | None, local_address: str = LOCAL) -> Neighbor:
    configured = negotiation.neighbor(local_address=local_address, peer_address=peer_address)
    configured.session.incoming_ttl = incoming_ttl
    return configured


@pytest.fixture
def freebsd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tcp.platform, 'system', lambda: 'FreeBSD')
    monkeypatch.delattr(tcp.socket, 'IP_MINTTL', raising=False)
    assert tcp.ip_minttl() == FREEBSD_IP_MINTTL


def listening_on(local: str) -> tuple[Listener, RecordingSocket]:
    reactor, _ = negotiation.reactor()
    serving = Listener(reactor)
    sock = RecordingSocket()
    serving._sockets[cast(Any, sock)] = (local, 179, '0.0.0.0', None, '')
    return serving, sock


@pytest.mark.rfc('rfc5082#3-must-not-drop-trusted-or-unknown')
def test_every_neighbour_asking_for_one_minimum_puts_it_on_the_listener(freebsd: Any) -> None:
    serving, sock = listening_on(LOCAL)

    serving.install_shared_minimum([gtsm('127.0.0.2', 254), gtsm('127.0.0.3', 254)])

    assert sock.minimum() == 254


@pytest.mark.rfc('rfc5082#3-must-not-drop-trusted-or-unknown', polarity='negative')
@pytest.mark.parametrize('other', [None, 200])
def test_a_neighbour_asking_for_another_minimum_or_none_leaves_the_listener_without(
    freebsd: Any, other: int | None
) -> None:
    """One minimum on the shared socket would drop the Unknown packets of the other."""
    serving, sock = listening_on(LOCAL)
    sock.options[(tcp.socket.IPPROTO_IP, FREEBSD_IP_MINTTL)] = 254  # what a previous configuration set

    serving.install_shared_minimum([gtsm('127.0.0.2', 254), gtsm('127.0.0.3', other)])

    assert sock.minimum() == 0


def test_a_neighbour_on_another_address_does_not_count(freebsd: Any) -> None:
    serving, sock = listening_on(LOCAL)

    serving.install_shared_minimum([gtsm('127.0.0.2', 254), gtsm('127.0.0.3', None, local_address='127.0.0.9')])

    assert sock.minimum() == 254


def test_a_wildcard_listener_is_behind_every_neighbour_of_its_family(freebsd: Any) -> None:
    serving, sock = listening_on('0.0.0.0')

    serving.install_shared_minimum([gtsm('127.0.0.2', 254), gtsm('127.0.0.3', None, local_address='127.0.0.9')])

    assert sock.minimum() == 0


def test_where_the_syn_is_kept_the_listener_carries_no_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    """Linux: the SYN is checked from its saved headers, the listener is left alone."""
    monkeypatch.setattr(tcp.platform, 'system', lambda: 'Linux')
    serving, sock = listening_on(LOCAL)

    serving.install_shared_minimum([gtsm('127.0.0.2', 254)])

    assert sock.options == {}


def test_where_there_is_no_minimum_option_nothing_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tcp.platform, 'system', lambda: 'Darwin')
    monkeypatch.delattr(tcp.socket, 'IP_MINTTL', raising=False)
    serving, sock = listening_on(LOCAL)

    serving.install_shared_minimum([gtsm('127.0.0.2', 254)])

    assert sock.options == {}


def test_the_accepted_socket_is_still_given_the_neighbour_minimum(freebsd: Any) -> None:
    """The check on the accepted socket stays: it is what covers a listener carrying none."""
    accepted_socket = RecordingSocket()
    # a real Incoming: a compiled listener takes nothing else, and calls the real
    # set_minimum_ttl, so the minimum is read back from the socket rather than from a
    # replaced name in the listener module, which only the interpreter would see
    accepted = Incoming(tcp.AFI.ipv4, LOCAL, LOCAL, cast(Any, accepted_socket))

    assert listener_module.admit_by_ttl(accepted, gtsm('127.0.0.2', 254))

    assert accepted_socket.minimum() == 254
