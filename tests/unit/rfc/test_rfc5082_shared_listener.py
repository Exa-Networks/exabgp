"""RFC 5082 on a listening socket every neighbour on the address shares.

The listener binds one socket per address, port and interface, and every neighbour on
it is behind that one socket. IP_MINTTL used to be installed there, from whichever
neighbour with `incoming-ttl` was configured last: a neighbour without GTSM then had its
SYNs dropped by a minimum it never asked for (Unknown packets, which section 3 says GTSM
MUST NOT drop), and two neighbours with different minimums dropped each other's. The
neighbours with no `listen` of their own went the other way: the global listener is set
up with no minimum, so `incoming-ttl` was never enforced on a session the peer opened.

Now the listening socket carries no minimum. Once an accepted connection is matched to
its neighbour, the TTL its SYN arrived with is checked against that neighbour's minimum
(Linux keeps the SYN's headers for us, TCP_SAVE_SYN), and the minimum is installed on the
accepted socket so every later segment is checked by the kernel.

These use real sockets on the loopback, so they run where the kernel has the options.
"""

from __future__ import annotations

import platform
import socket
from collections.abc import Iterator
import pytest

from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP
from exabgp.reactor import listener as listener_module
from exabgp.reactor.listener import Listener
from exabgp.reactor.loop import Reactor
from exabgp.reactor.network import tcp
from exabgp.reactor.network.incoming import Incoming
from exabgp.reactor.peer import Peer
from tests import negotiation

pytestmark = pytest.mark.skipif(platform.system() != 'Linux', reason='IP_MINTTL and TCP_SAVE_SYN are Linux options')

GTSM_MINIMUM = 254
LOCAL = '127.0.0.1'
PEER = '127.0.0.2'
IP_MINTTL = 21  # linux/in.h


def free_port() -> int:
    probe = socket.socket()
    probe.bind((LOCAL, 0))
    port: int = probe.getsockname()[1]
    probe.close()
    return port


def gtsm_neighbor(incoming_ttl: int | None) -> Neighbor:
    configured = negotiation.neighbor(local_address=LOCAL, peer_address=PEER)
    configured.session.incoming_ttl = incoming_ttl
    return configured


@pytest.fixture
def peer() -> Peer:
    """A real neighbour asking for GTSM, on a real reactor: the compiled Listener takes nothing else."""
    built: Peer
    built, _ = negotiation.peer(gtsm_neighbor(GTSM_MINIMUM))
    built.reactor.register_peer('peer', built)
    return built


@pytest.fixture
def listening(peer: Peer) -> Iterator[tuple[Listener, int]]:
    serving = Listener(peer.reactor)
    yield serving, free_port()
    serving.stop()


def connect(port: int, sent_ttl: int) -> socket.socket:
    client = socket.socket()
    client.settimeout(2)
    client.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, sent_ttl)
    client.bind((PEER, 0))
    client.connect((LOCAL, port))
    return client


def accept(serving: Listener) -> Incoming:
    sock = next(iter(serving._sockets))
    sock.settimeout(2)
    io, _ = sock.accept()
    return Incoming(AFI.ipv4, LOCAL, PEER, io)


def listen_for(serving: Listener, port: int, peer: str) -> None:
    assert serving.listen_on(IP.from_string(LOCAL), IP.from_string(peer), port, None, False)


def two_neighbours_sharing_a_listener(port: int) -> Reactor:
    """127.0.0.3 asks for GTSM, 127.0.0.2 does not, and both listen on one address and port."""
    text = ''
    for address, ttl in (('127.0.0.3', f'incoming-ttl {GTSM_MINIMUM};'), (PEER, '')):
        text += f"""
neighbor {address} {{
    router-id {LOCAL};
    local-address {LOCAL};
    local-as 65001;
    peer-as 65002;
    listen {port};
    {ttl}
    family {{ ipv4 unicast; }}
}}
"""
    configuration = Configuration([text], text=True)
    assert configuration.reload(), str(configuration.error)
    reactor = Reactor(configuration)
    reactor._ips = []
    return reactor


@pytest.mark.rfc('rfc5082#3-must-not-drop-trusted-or-unknown')
def test_a_neighbour_without_gtsm_is_not_dropped_by_the_minimum_of_one_sharing_its_listener() -> None:
    """The audit's case: one neighbour asks for 254, the other for nothing and connects with TTL 64."""
    reactor = two_neighbours_sharing_a_listener(free_port())
    try:
        assert reactor._listen_for_neighbors()
        sockets = list(reactor.listener._sockets)
        assert len(sockets) == 1, 'the two neighbours are meant to share one listening socket'
        assert sockets[0].getsockopt(socket.IPPROTO_IP, IP_MINTTL) == 0, (
            'a minimum TTL was installed on a listener shared with a neighbour which never asked for GTSM'
        )

        client = connect(reactor.listener._sockets[sockets[0]][1], 64)
        accept(reactor.listener).close()
        client.close()
    finally:
        reactor.listener.stop()


@pytest.mark.rfc('rfc5082#3-must-not-drop-trusted-or-unknown')
def test_a_gtsm_neighbour_sending_255_is_accepted_and_its_session_keeps_the_minimum(
    listening: tuple[Listener, int], peer: Peer
) -> None:
    serving, port = listening
    listen_for(serving, port, PEER)

    client = connect(port, 255)
    connection = accept(serving)
    serving._dispatch(connection)

    assert peer.proto is not None, 'a Trusted connection was not handed to its neighbour'
    assert connection.io is not None
    assert connection.io.getsockopt(socket.IPPROTO_IP, IP_MINTTL) == GTSM_MINIMUM, (
        'the accepted session was left without the neighbour minimum, so later segments are not checked'
    )
    connection.close()
    client.close()


@pytest.mark.rfc('rfc5082#3-must-not-drop-trusted-or-unknown', polarity='negative')
def test_a_gtsm_neighbour_whose_syn_arrived_below_the_minimum_is_dropped(
    listening: tuple[Listener, int], peer: Peer
) -> None:
    """Through a listener with no minimum of its own: the global listener's case."""
    serving, port = listening
    listen_for(serving, port, PEER)

    client = connect(port, 64)
    connection = accept(serving)
    serving._dispatch(connection)

    assert peer.proto is None, 'a connection which arrived with TTL 64 was given to a neighbour asking for 254'
    assert connection.io is None, 'the Dangerous connection was left open'
    client.close()


def test_the_ttl_of_the_syn_is_read_from_the_saved_headers(listening: tuple[Listener, int]) -> None:
    serving, port = listening
    listen_for(serving, port, PEER)

    client = connect(port, 200)
    connection = accept(serving)

    assert connection.io is not None
    assert tcp.saved_syn_ttl(connection.io) == 200
    connection.close()
    client.close()


def test_a_gtsm_check_with_no_saved_syn_admits_and_still_installs_the_minimum() -> None:
    """Where the kernel kept no SYN the first segment can not be checked: the rest still are.

    The listening socket here never asked for TCP_SAVE_SYN, which is what a kernel without
    the option looks like from this side.
    """
    server = socket.socket()
    server.bind((LOCAL, 0))
    server.listen(1)
    client = socket.socket()
    client.bind((PEER, 0))
    client.connect(server.getsockname())
    io, _ = server.accept()
    connection = Incoming(AFI.ipv4, LOCAL, PEER, io)

    assert tcp.saved_syn_ttl(io) is None
    assert listener_module.admit_by_ttl(connection, gtsm_neighbor(GTSM_MINIMUM))
    assert io.getsockopt(socket.IPPROTO_IP, IP_MINTTL) == GTSM_MINIMUM
    connection.close()
    client.close()
    server.close()
