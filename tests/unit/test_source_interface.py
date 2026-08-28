"""test_source_interface.py

source-interface binds a session to one device. That is what makes a link-local
address usable at all, since the kernel refuses to bind or connect one until the
socket names a link, so the interface is part of what a neighbour is rather than
a detail of how it connects.

License: 3-clause BSD
"""

from __future__ import annotations

import copy
import socket

import pytest

from exabgp.configuration.configuration import Configuration
from exabgp.reactor.network.error import NotConnected
from exabgp.reactor.network.tcp import bind_to_device


def _parse(cfg: str) -> tuple[bool, Configuration]:
    c = Configuration([cfg], text=True)
    ok = c.reload()
    return ok, c


def _neighbor(peer: str = 'fe80::1', interface: str = 'eth0', local: str = 'fe80::2') -> str:
    device = f'    source-interface {interface};\n' if interface else ''
    return f"""neighbor {peer} {{
    router-id 10.0.0.2;
    local-address {local};
{device}    local-as 65001;
    peer-as 65000;
    capability {{ link-local-nexthop enable; }}
}}"""


# ==============================================================================
# The interface is part of the neighbour's identity
# ==============================================================================


def test_two_neighbours_may_share_a_link_local_address_on_different_links() -> None:
    ok, c = _parse(_neighbor(interface='eth0') + '\n' + _neighbor(interface='eth1'))

    assert ok, c.error
    assert len(c.neighbors) == 2


def test_the_same_neighbour_twice_is_still_a_duplicate() -> None:
    ok, c = _parse(_neighbor(interface='eth0') + '\n' + _neighbor(interface='eth0'))

    assert not ok
    assert 'duplicate peer definition' in str(c.error)


def test_the_name_carries_the_interface_only_when_one_is_set() -> None:
    ok, c = _parse(_neighbor(interface='eth0'))
    assert ok, c.error
    assert 'source-interface eth0' in next(iter(c.neighbors.values())).name()

    ok, c = _parse(_neighbor(peer='192.0.2.1', interface='', local='192.0.2.2'))
    assert ok, c.error
    assert 'source-interface' not in next(iter(c.neighbors.values())).name()


def test_moving_a_session_to_another_interface_is_a_change() -> None:
    ok, c = _parse(_neighbor(interface='eth0'))
    assert ok, c.error
    neighbor = next(iter(c.neighbors.values()))

    unchanged = copy.deepcopy(neighbor)
    assert neighbor == unchanged

    moved = copy.deepcopy(neighbor)
    moved.session.source_interface = 'eth1'
    assert neighbor != moved


# ==============================================================================
# The shape of the name is configuration, its existence is the host's business
# ==============================================================================


def test_a_name_longer_than_the_kernel_allows_is_refused() -> None:
    ok, c = _parse(_neighbor(interface='an-interface-name-far-too-long'))

    assert not ok
    assert 'longer than 15 characters' in str(c.error)


def test_a_name_which_can_not_be_a_device_is_refused() -> None:
    # a space never survives the tokeniser, so a path separator is what is left
    # to reject in a configuration file
    ok, c = _parse(_neighbor(interface='eth/0'))

    assert not ok
    assert 'not a valid interface name' in str(c.error)


def test_a_name_which_no_device_carries_still_parses() -> None:
    # whether eth42 exists is not something a configuration file can know, and a
    # config checked on one host is often deployed on another
    ok, c = _parse(_neighbor(interface='eth42'))

    assert ok, c.error


# ==============================================================================
# Binding says what went wrong
# ==============================================================================


def test_binding_to_an_unknown_device_names_the_device() -> None:
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        with pytest.raises(NotConnected, match='no-such-device'):
            bind_to_device(sock, 'no-such-device')
    finally:
        sock.close()


@pytest.mark.skipif(hasattr(socket, 'SO_BINDTODEVICE'), reason='the option exists on this platform')
def test_binding_says_so_where_the_option_does_not_exist() -> None:
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        with pytest.raises(NotConnected, match='only exists on Linux'):
            bind_to_device(sock, 'lo')
    finally:
        sock.close()
