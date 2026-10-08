"""What a reload leaves behind has to match what the configuration asks for.

`tests/unit/test_reactor_signal.py` covers signal *delivery* thoroughly, and nothing
covered what the reload those signals trigger actually does to the reactor. That is the
hole issue #1425 fell through: a neighbour commented out and the configuration reloaded
left its peer in `show neighbor summary` and its port bound and accepting, for the life
of the process.

The two invariants below are what that bug broke, stated once so every shape of
configuration change is held to them rather than only the shape which was reported:

    the peers held      ==  the neighbours configured, plus those still finishing
    the sockets bound   ==  the (address, port) pairs the configuration asks for

A peer which has been removed is allowed to still be in `_peers` immediately after the
reload, because it is dropped on its next turn rather than synchronously. What it may not
be is *unreapable*, so the peers which survive are required to be on their way out.

No daemon runs, but the sockets are real: the reactor is compiled, and refuses a listener
which is not a Listener, so the real one binds unprivileged ports on 127.0.0.1 and what is
bound is read back from it. `tests/unit/test_removed_neighbor_cleanup.py` covers the socket
handling itself.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock, patch

import pytest

os.environ['exabgp_log_enable'] = 'false'
os.environ['exabgp_log_level'] = 'CRITICAL'

from exabgp.bgp.neighbor import Neighbor  # noqa: E402
from exabgp.protocol.ip import IP  # noqa: E402
from exabgp.reactor.loop import Reactor  # noqa: E402
from exabgp.reactor.peer.peer import Peer  # noqa: E402
from tests import negotiation  # noqa: E402


def free_ports(count: int) -> list[int]:
    """Unprivileged ports nothing listens on: the kernel picks them, then they are let go."""
    held = [socket.create_server(('127.0.0.1', 0)) for _ in range(count)]
    ports = [held_socket.getsockname()[1] for held_socket in held]
    for held_socket in held:
        held_socket.close()
    return ports


# The global listener's port (the -l addresses) and two neighbour `listen` ports
GLOBAL_PORT, PORT_A, PORT_B = free_ports(3)

# every reactor a test built, so its listening sockets are closed whatever the test did
BUILT: list[Reactor] = []


@pytest.fixture(autouse=True)
def mock_logger() -> Any:
    """The reactor logs on every path taken here."""
    from exabgp.logger.option import option

    logger = option.logger
    formater = option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger = logger
    option.formater = formater


@pytest.fixture(autouse=True)
def release_ports() -> Iterator[None]:
    yield
    for reactor in BUILT:
        reactor.listener.stop()
    BUILT.clear()


class Configured:
    """The configuration as the reactor reads it: the neighbours, and a reload which works."""

    def __init__(self, neighbors: dict[str, Neighbor]) -> None:
        self.neighbors = neighbors
        self.error = ''

    def reload(self) -> bool:
        return True


def neighbor(peer_address: str, listen_port: int = 0, local_address: str = '127.0.0.1') -> Neighbor:
    """A configured passive neighbour, as the reactor reads one."""
    configured = negotiation.api_asks(negotiation.neighbor(peer_address=peer_address, local_address=local_address))
    configured.session.md5_ip = IP.from_string(local_address)
    configured.session.listen = listen_port
    configured.session.passive = True
    return configured


def reactor_serving(neighbors: dict[str, Neighbor], listen_ips: list[str] | None = None) -> Reactor:
    """A reactor holding that configuration, with nothing bound yet."""
    reactor = Reactor(Configured(neighbors))
    reactor._ips = [IP.from_string(ip) for ip in (listen_ips or ['127.0.0.1'])]
    reactor._port = GLOBAL_PORT
    BUILT.append(reactor)
    return reactor


def bound(reactor: Reactor) -> set[tuple[str, int]]:
    """The (address, port) pairs the reactor's listener has a socket bound to."""
    return {(local, port) for (local, port, _, _, _) in reactor.listener._sockets.values()}


@contextmanager
def occupied(port: int) -> Iterator[None]:
    """Something else listening on 127.0.0.1:port, so the listener can not bind it."""
    with socket.create_server(('127.0.0.1', port)):
        yield


def wanted_sockets(reactor: Any) -> set[tuple[str, int]]:
    """What the configuration asks to be listening on, computed from the configuration."""
    wanted = {(ip.top(), reactor._port) for ip in reactor._ips}
    for configured in reactor.configuration.neighbors.values():
        if configured.session.listen:
            wanted.add((configured.session.md5_ip.top(), configured.session.listen))
    return wanted


def assert_invariants(reactor: Any) -> None:
    """The two things which must be true after any reload."""
    configured = set(reactor.configuration.neighbors)
    held = set(reactor._peers)

    # A peer is dropped on its next turn, so one may still be here immediately after the
    # reload. What it may not be is unreapable, and the reactor only ever drops a peer it
    # runs: asking active_peers() states that without leaning on anything the fix added,
    # so this fails on the defect rather than on a missing helper.
    surplus = held - configured
    never_run = surplus - reactor.active_peers()
    assert not never_run, f'peers held for neighbours which are gone and will never be dropped: {never_run}'

    missing = configured - held
    assert not missing, f'configured neighbours with no peer: {missing}'

    assert bound(reactor) == wanted_sockets(reactor), (
        f'bound {bound(reactor)} but the configuration asks for {wanted_sockets(reactor)}'
    )


def test_the_invariants_hold_on_a_first_load() -> None:
    reactor = reactor_serving({'a': neighbor('127.0.0.2', PORT_A)})

    assert reactor.reload()

    assert_invariants(reactor)
    assert ('127.0.0.1', PORT_A) in bound(reactor)


def test_removing_a_neighbour_releases_its_peer_and_its_port() -> None:
    """Issue #1425. The peer stayed forever and the port stayed bound and accepting."""
    neighbors = {'a': neighbor('127.0.0.2', PORT_A), 'b': neighbor('127.0.0.3')}
    reactor = reactor_serving(neighbors)
    assert reactor.reload()

    del neighbors['a']

    assert reactor.reload()
    assert_invariants(reactor)
    assert ('127.0.0.1', PORT_A) not in bound(reactor), 'the removed neighbour kept its port'
    assert 'a' in reactor.active_peers(), 'the removed peer is never run, so it is never dropped'


def test_adding_a_neighbour_binds_its_port_without_a_restart() -> None:
    """The same bug from the other side: this used to need the daemon restarted."""
    neighbors: dict[str, Neighbor] = {'b': neighbor('127.0.0.3')}
    reactor = reactor_serving(neighbors)
    assert reactor.reload()
    assert ('127.0.0.1', PORT_A) not in bound(reactor)

    neighbors['a'] = neighbor('127.0.0.2', PORT_A)

    assert reactor.reload()
    assert_invariants(reactor)
    assert ('127.0.0.1', PORT_A) in bound(reactor), 'a neighbour added by a reload never listened'


def test_moving_a_neighbour_to_another_port_releases_the_old_one() -> None:
    neighbors = {'a': neighbor('127.0.0.2', PORT_A)}
    reactor = reactor_serving(neighbors)
    assert reactor.reload()

    neighbors['a'] = neighbor('127.0.0.2', PORT_B)

    assert reactor.reload()
    assert_invariants(reactor)
    assert ('127.0.0.1', PORT_A) not in bound(reactor), 'the port it moved off stayed bound'
    assert ('127.0.0.1', PORT_B) in bound(reactor)


def test_two_neighbours_on_one_port_keep_it_until_both_are_gone() -> None:
    """A socket is shared per (address, port), so removing one neighbour must not close it.

    This is the case a reference count gets wrong, and the reason close_unwanted is told
    what the configuration wants rather than what to remove.
    """
    neighbors = {'a': neighbor('127.0.0.2', PORT_A), 'b': neighbor('127.0.0.3', PORT_A)}
    reactor = reactor_serving(neighbors)
    assert reactor.reload()

    del neighbors['a']

    assert reactor.reload()
    assert_invariants(reactor)
    assert ('127.0.0.1', PORT_A) in bound(reactor), 'a port another neighbour still uses was closed'

    del neighbors['b']

    assert reactor.reload()
    assert_invariants(reactor)
    assert ('127.0.0.1', PORT_A) not in bound(reactor)


def test_the_global_listener_survives_every_neighbour_going_away() -> None:
    """The -l addresses are not a neighbour's to release."""
    neighbors = {'a': neighbor('127.0.0.2', PORT_A)}
    reactor = reactor_serving(neighbors)
    assert reactor.reload()

    neighbors.clear()

    assert reactor.reload()
    assert_invariants(reactor)
    assert ('127.0.0.1', GLOBAL_PORT) in bound(reactor), 'the global listener was closed'


def test_a_removed_peer_is_the_only_peer_allowed_to_outlive_its_neighbour() -> None:
    """A peer left behind for any other reason is the #1425 leak wearing a different hat."""
    neighbors = {'a': neighbor('127.0.0.2', PORT_A)}
    reactor = reactor_serving(neighbors)
    assert reactor.reload()

    stranger = Peer(neighbor('127.0.0.9'), reactor)
    reactor._peers['stranger'] = stranger

    with pytest.raises(AssertionError, match='never be dropped'):
        assert_invariants(reactor)


# The four below were written because mutation testing said the tests above run
# _listen_for_neighbors() without defending it: the flag it returns could be hardcoded,
# the skip could become a break, and every argument past the port could become None,
# and the suite stayed green through all of it.


def test_a_port_which_will_not_bind_is_reported() -> None:
    """run() turns a False here into a refusal to start, so the flag has to be real."""
    neighbors = {'a': neighbor('127.0.0.2', PORT_A)}
    reactor = reactor_serving(neighbors)

    with occupied(PORT_A):
        assert not reactor._listen_for_neighbors(), 'a port which would not bind was reported as bound'


def test_every_port_binding_is_reported_as_success() -> None:
    """The control for the test above: False means something only if True is reachable."""
    neighbors = {'a': neighbor('127.0.0.2', PORT_A)}
    reactor = reactor_serving(neighbors)

    assert reactor._listen_for_neighbors()


def test_a_neighbour_without_a_listen_port_does_not_hide_the_ones_after_it() -> None:
    """The skip has to be a continue: a break drops every neighbour past the first one."""
    neighbors = {'plain': neighbor('127.0.0.3'), 'listening': neighbor('127.0.0.2', PORT_A)}
    reactor = reactor_serving(neighbors)

    assert reactor._listen_for_neighbors()
    assert ('127.0.0.1', PORT_A) in bound(reactor), 'a neighbour behind one with no listen port was lost'


# linux/tcp.h and linux/in.h: the options the key and the minimum TTL are installed with
TCP_MD5SIG = 14
IP_MINTTL = 21
# the TCP_MD5SIG option is a 128 byte __kernel_sockaddr_storage followed by tcp_md5sig
SOCKADDR_STORAGE_BYTES = 128


def test_a_neighbour_passes_its_authentication_to_its_socket() -> None:
    """The address and the port are not the whole call: an MD5 key which never reaches the
    socket is a session which will not come up, and the reload path had nothing saying so.

    Run as on Linux, where the key and a minimum TTL can both be installed, with the socket
    options recorded rather than set: what is asserted is what the kernel is asked for on
    the neighbour's socket, the key and no minimum TTL.
    """
    configured = neighbor('127.0.0.2', PORT_A)
    configured.session.md5_password = 'a-secret'
    configured.session.incoming_ttl = 254
    reactor = reactor_serving({'a': configured})
    options: list[tuple[int, int, int | bytes]] = []

    # only the neighbour's socket is made here: the global listener is bound by reload()
    def setsockopt(sock: socket.socket, level: int, option: int, value: int | bytes) -> None:
        options.append((level, option, value))

    with patch('platform.system', return_value='Linux'), patch.object(socket.socket, 'setsockopt', setsockopt):
        assert reactor._listen_for_neighbors()

    assert ('127.0.0.1', PORT_A) in bound(reactor), 'the neighbour never asked for its port'
    keys = [value for level, option, value in options if (level, option) == (socket.IPPROTO_TCP, TCP_MD5SIG)]
    assert keys and isinstance(keys[0], bytes), 'the md5 password did not reach the socket'
    assert b'a-secret' in keys[0][SOCKADDR_STORAGE_BYTES:], 'the md5 password did not reach the socket'
    # RFC 5082 3: the listening socket is shared by every neighbour on the address, so the
    # minimum is installed per neighbour on the accepted socket (Listener admit_by_ttl)
    assert not [o for o in options if o[:2] == (socket.IPPROTO_IP, IP_MINTTL)], 'a minimum TTL was set on a listener'


def test_two_neighbours_on_different_ports_both_listen() -> None:
    """There are two skips in that loop and both have to be a continue.

    The one after a successful bind is invisible with a single listening neighbour, which
    is what let a break survive there.
    """
    neighbors = {'first': neighbor('127.0.0.2', PORT_A), 'second': neighbor('127.0.0.3', PORT_B)}
    reactor = reactor_serving(neighbors)

    assert reactor._listen_for_neighbors()
    assert ('127.0.0.1', PORT_A) in bound(reactor)
    assert ('127.0.0.1', PORT_B) in bound(reactor), 'the second listening neighbour never bound'
