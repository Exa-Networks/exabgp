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

No sockets are bound here and no daemon runs. `Listener` is a double which records what it
was asked to bind, which is enough: what is under test is the reactor's bookkeeping, and
`tests/unit/test_removed_neighbor_cleanup.py` covers the socket handling itself.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest

os.environ['exabgp_log_enable'] = 'false'
os.environ['exabgp_log_level'] = 'CRITICAL'

from exabgp.protocol.family import AFI  # noqa: E402
from exabgp.protocol.ip import IP  # noqa: E402
from exabgp.reactor.loop import Reactor  # noqa: E402
from exabgp.reactor.peer.peer import Peer  # noqa: E402

GLOBAL_PORT = 179


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


class FakeListener:
    """Records what it was asked to bind, and honours close_unwanted the way Listener does.

    It shares one entry per (address, port) on purpose. That sharing is why the real
    close_unwanted takes the set of pairs the configuration wants rather than removing one
    neighbour's socket: several neighbours sit behind one entry and nothing records how
    many.
    """

    def __init__(self, refuse: set[tuple[str, int]] | None = None) -> None:
        self.bound: set[tuple[str, int]] = set()
        self.serving: bool = False
        self.refuse: set[tuple[str, int]] = refuse or set()
        # every argument of every call, so a test can say the authentication a neighbour
        # asked for actually reached the socket rather than only its address and port
        self.calls: list[tuple[Any, ...]] = []

    def listen_on(self, local_addr: IP, remote_addr: Any, port: int, *arguments: Any) -> bool:
        self.calls.append((local_addr.top(), remote_addr, port, *arguments))
        if (local_addr.top(), port) in self.refuse:
            return False
        self.bound.add((local_addr.top(), port))
        self.serving = True
        return True

    def close_unwanted(self, wanted: set[tuple[str, int]]) -> None:
        self.bound &= wanted
        self.serving = bool(self.bound)


def neighbor(peer_address: str, listen_port: int | None = None, local_address: str = '127.0.0.1') -> Any:
    """A configured neighbour, as the reactor reads one."""
    configured = MagicMock()
    configured.session.peer_address = IP.from_string(peer_address)
    configured.session.peer_address.afi = AFI.ipv4
    configured.session.local_address = IP.from_string(local_address)
    configured.session.md5_ip = IP.from_string(local_address)
    configured.session.listen = listen_port
    configured.session.passive = True
    configured.session.md5_password = None
    configured.session.md5_base64 = False
    configured.session.incoming_ttl = None
    configured.session.tcp_ao_keyid = None
    configured.session.tcp_ao_algorithm = ''
    configured.session.tcp_ao_password = ''
    configured.session.tcp_ao_base64 = False
    configured.session.source_interface = ''
    configured.name.return_value = f'neighbor {peer_address}'
    configured.rib = Mock()
    configured.api = {'neighbor-changes': False, 'fsm': False}
    return configured


def reactor_serving(neighbors: dict[str, Any], listen_ips: list[str] | None = None) -> Any:
    """A reactor holding that configuration, with nothing bound yet."""
    reactor = Reactor.__new__(Reactor)
    reactor._peers = {}
    reactor._ips = [IP.from_string(ip) for ip in (listen_ips or ['127.0.0.1'])]
    reactor._port = GLOBAL_PORT
    reactor.listener = FakeListener()
    reactor.configuration = MagicMock()
    reactor.configuration.neighbors = neighbors
    reactor.configuration.reload.return_value = True
    return reactor


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

    assert reactor.listener.bound == wanted_sockets(reactor), (
        f'bound {reactor.listener.bound} but the configuration asks for {wanted_sockets(reactor)}'
    )


def test_the_invariants_hold_on_a_first_load() -> None:
    reactor = reactor_serving({'a': neighbor('127.0.0.2', 1179)})

    assert reactor.reload()

    assert_invariants(reactor)
    assert ('127.0.0.1', 1179) in reactor.listener.bound


def test_removing_a_neighbour_releases_its_peer_and_its_port() -> None:
    """Issue #1425. The peer stayed forever and the port stayed bound and accepting."""
    neighbors = {'a': neighbor('127.0.0.2', 1179), 'b': neighbor('127.0.0.3')}
    reactor = reactor_serving(neighbors)
    assert reactor.reload()

    del neighbors['a']

    assert reactor.reload()
    assert_invariants(reactor)
    assert ('127.0.0.1', 1179) not in reactor.listener.bound, 'the removed neighbour kept its port'
    assert 'a' in reactor.active_peers(), 'the removed peer is never run, so it is never dropped'


def test_adding_a_neighbour_binds_its_port_without_a_restart() -> None:
    """The same bug from the other side: this used to need the daemon restarted."""
    neighbors: dict[str, Any] = {'b': neighbor('127.0.0.3')}
    reactor = reactor_serving(neighbors)
    assert reactor.reload()
    assert ('127.0.0.1', 1179) not in reactor.listener.bound

    neighbors['a'] = neighbor('127.0.0.2', 1179)

    assert reactor.reload()
    assert_invariants(reactor)
    assert ('127.0.0.1', 1179) in reactor.listener.bound, 'a neighbour added by a reload never listened'


def test_moving_a_neighbour_to_another_port_releases_the_old_one() -> None:
    neighbors = {'a': neighbor('127.0.0.2', 1179)}
    reactor = reactor_serving(neighbors)
    assert reactor.reload()

    neighbors['a'] = neighbor('127.0.0.2', 1180)

    assert reactor.reload()
    assert_invariants(reactor)
    assert ('127.0.0.1', 1179) not in reactor.listener.bound, 'the port it moved off stayed bound'
    assert ('127.0.0.1', 1180) in reactor.listener.bound


def test_two_neighbours_on_one_port_keep_it_until_both_are_gone() -> None:
    """A socket is shared per (address, port), so removing one neighbour must not close it.

    This is the case a reference count gets wrong, and the reason close_unwanted is told
    what the configuration wants rather than what to remove.
    """
    neighbors = {'a': neighbor('127.0.0.2', 1179), 'b': neighbor('127.0.0.3', 1179)}
    reactor = reactor_serving(neighbors)
    assert reactor.reload()

    del neighbors['a']

    assert reactor.reload()
    assert_invariants(reactor)
    assert ('127.0.0.1', 1179) in reactor.listener.bound, 'a port another neighbour still uses was closed'

    del neighbors['b']

    assert reactor.reload()
    assert_invariants(reactor)
    assert ('127.0.0.1', 1179) not in reactor.listener.bound


def test_the_global_listener_survives_every_neighbour_going_away() -> None:
    """The -l addresses are not a neighbour's to release."""
    neighbors = {'a': neighbor('127.0.0.2', 1179)}
    reactor = reactor_serving(neighbors)
    assert reactor.reload()

    neighbors.clear()

    assert reactor.reload()
    assert_invariants(reactor)
    assert ('127.0.0.1', GLOBAL_PORT) in reactor.listener.bound, 'the global listener was closed'


def test_a_removed_peer_is_the_only_peer_allowed_to_outlive_its_neighbour() -> None:
    """A peer left behind for any other reason is the #1425 leak wearing a different hat."""
    neighbors = {'a': neighbor('127.0.0.2', 1179)}
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
    neighbors = {'a': neighbor('127.0.0.2', 1179)}
    reactor = reactor_serving(neighbors)
    reactor.listener.refuse = {('127.0.0.1', 1179)}

    assert not reactor._listen_for_neighbors(), 'a port which would not bind was reported as bound'


def test_every_port_binding_is_reported_as_success() -> None:
    """The control for the test above: False means something only if True is reachable."""
    neighbors = {'a': neighbor('127.0.0.2', 1179)}
    reactor = reactor_serving(neighbors)

    assert reactor._listen_for_neighbors()


def test_a_neighbour_without_a_listen_port_does_not_hide_the_ones_after_it() -> None:
    """The skip has to be a continue: a break drops every neighbour past the first one."""
    neighbors = {'plain': neighbor('127.0.0.3'), 'listening': neighbor('127.0.0.2', 1179)}
    reactor = reactor_serving(neighbors)

    assert reactor._listen_for_neighbors()
    assert ('127.0.0.1', 1179) in reactor.listener.bound, 'a neighbour behind one with no listen port was lost'


def test_a_neighbour_passes_its_authentication_to_its_socket() -> None:
    """The address and the port are not the whole call: an MD5 key which never reaches the
    socket is a session which will not come up, and the reload path had nothing saying so.
    """
    configured = neighbor('127.0.0.2', 1179)
    configured.session.md5_password = 'a-secret'
    configured.session.incoming_ttl = 254
    reactor = reactor_serving({'a': configured})

    assert reactor._listen_for_neighbors()

    listening = [call for call in reactor.listener.calls if call[2] == 1179]
    assert listening, 'the neighbour never asked for its port'
    assert 'a-secret' in listening[0], 'the md5 password did not reach the socket'
    assert 254 in listening[0], 'the incoming ttl did not reach the socket'


def test_two_neighbours_on_different_ports_both_listen() -> None:
    """There are two skips in that loop and both have to be a continue.

    The one after a successful bind is invisible with a single listening neighbour, which
    is what let a break survive there.
    """
    neighbors = {'first': neighbor('127.0.0.2', 1179), 'second': neighbor('127.0.0.3', 1180)}
    reactor = reactor_serving(neighbors)

    assert reactor._listen_for_neighbors()
    assert ('127.0.0.1', 1179) in reactor.listener.bound
    assert ('127.0.0.1', 1180) in reactor.listener.bound, 'the second listening neighbour never bound'
