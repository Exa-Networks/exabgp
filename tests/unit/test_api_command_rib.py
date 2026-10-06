"""The adj-rib commands: show, flush and clear.

    rib show in | out [<ip>] [extensive] [inet|flow|l2vpn]
    rib flush out, rib clear in | out

and the API 4 forms, `show adj-rib ...`, `flush adj-rib out`, `clear adj-rib ...`. Each runs
on a real Reactor (tests/api_daemon.py) with two neighbors, and is checked against what the
RIB of each neighbor holds.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.api_daemon import FIRST, SECOND, Daemon, answer

VPLS = 'vpls endpoint 10 offset 20 size 8 base 203 rd 1:1'


@pytest.fixture
def daemon() -> Iterator[Daemon]:
    created = Daemon()
    yield created
    created.close()


@pytest.fixture
def text_daemon() -> Iterator[Daemon]:
    """A daemon whose helper is configured `encoder text`, for the API 4 forms."""
    created = Daemon(encoder='text')
    yield created
    created.close()


def populate(daemon: Daemon, api_4: bool = False) -> None:
    """A route to both neighbors, and a flow and a VPLS route to the first, which alone carries them."""
    prefix = '' if api_4 else 'peer *'
    for route in (
        'route 10.0.0.0/24 next-hop 1.2.3.4',
        'flow route destination 10.0.0.0/24 discard',
        f'{VPLS} next-hop 1.2.3.4',
    ):
        assert daemon.send(f'{prefix} announce {route}'.strip()) == ['done']


def received(daemon: Daemon, address: str) -> list[str]:
    return sorted(str(route.nlri) for route in daemon.neighbor(address).rib.incoming.cached_routes(None))


def receive(daemon: Daemon, address: str, prefix: str) -> None:
    """Put a route in the adj-rib-in of a neighbor, as one received from it."""
    daemon.send(f'peer {address} announce route {prefix} next-hop 1.2.3.4')
    outgoing = daemon.neighbor(address).rib.outgoing
    (route,) = [route for route in outgoing.cached_routes(None) if str(route.nlri) == prefix]
    outgoing.withdraw()
    outgoing.reset()
    daemon.neighbor(address).rib.incoming.update_cache(route)


# ============================================================================== show


def test_show_out_in_json_is_a_line_per_route(daemon: Daemon) -> None:
    populate(daemon)
    lines = daemon.send('rib show out')
    assert answer(lines) == [
        {FIRST: {'routes': [{'family': 'ipv4 unicast', 'prefix': '10.0.0.0/24'}]}},
        {FIRST: {'routes': [{'family': 'ipv4 flow', 'nlri': 'flow destination-ipv4 10.0.0.0/24'}]}},
        {FIRST: {'routes': [{'family': 'l2vpn vpls', 'nlri': 'vpls rd 1:1 endpoint 10 base 203 offset 20 size 8'}]}},
        {SECOND: {'routes': [{'family': 'ipv4 unicast', 'prefix': '10.0.0.0/24'}]}},
    ]
    assert lines[-1] == 'done'


def test_show_out_extensive_in_json_adds_the_neighbor(daemon: Daemon) -> None:
    daemon.send(f'peer {SECOND} announce route 10.0.0.0/24 next-hop 1.2.3.4')
    (shown,) = answer(daemon.send('rib show out extensive'))
    assert shown[SECOND]['routes'] == [{'family': 'ipv4 unicast', 'prefix': '10.0.0.0/24'}]
    assert shown[SECOND]['peer-address'] == SECOND
    assert 'state' in shown[SECOND]


def test_show_out_in_text(text_daemon: Daemon) -> None:
    populate(text_daemon, api_4=True)
    assert text_daemon.send('show adj-rib out') == [
        f'{FIRST} ipv4 unicast 10.0.0.0/24',
        f'{FIRST} ipv4 flow flow destination-ipv4 10.0.0.0/24',
        f'{FIRST} l2vpn vpls vpls rd 1:1 endpoint 10 base 203 offset 20 size 8',
        f'{SECOND} ipv4 unicast 10.0.0.0/24',
        'done',
    ]


def test_show_out_extensive_in_text_names_the_neighbor_and_the_attributes(text_daemon: Daemon) -> None:
    text_daemon.send(f'neighbor {SECOND} announce route 10.0.0.0/24 next-hop 1.2.3.4 med 5')
    assert text_daemon.send('show adj-rib out extensive') == [
        f'{text_daemon.key(SECOND)} ipv4 unicast 10.0.0.0/24 next-hop 1.2.3.4 med 5',
        'done',
    ]


@pytest.mark.parametrize(
    ('kind', 'shown'),
    [
        ('inet', [f'{FIRST} ipv4 unicast 10.0.0.0/24', f'{SECOND} ipv4 unicast 10.0.0.0/24']),
        ('flow', [f'{FIRST} ipv4 flow flow destination-ipv4 10.0.0.0/24']),
        ('l2vpn', [f'{FIRST} l2vpn vpls vpls rd 1:1 endpoint 10 base 203 offset 20 size 8']),
    ],
)
def test_show_out_of_one_kind_of_route(text_daemon: Daemon, kind: str, shown: list[str]) -> None:
    populate(text_daemon, api_4=True)
    assert text_daemon.send(f'show adj-rib out {kind}') == shown + ['done']


def test_show_out_of_one_neighbor(text_daemon: Daemon) -> None:
    populate(text_daemon, api_4=True)
    assert text_daemon.send(f'show adj-rib out {SECOND}') == [f'{SECOND} ipv4 unicast 10.0.0.0/24', 'done']


def test_show_in(daemon: Daemon) -> None:
    receive(daemon, SECOND, '10.9.0.0/24')
    lines = daemon.send('rib show in')
    assert answer(lines) == [{SECOND: {'routes': [{'family': 'ipv4 unicast', 'prefix': '10.9.0.0/24'}]}}]
    assert lines[-1] == 'done'


def test_show_of_an_empty_rib_is_done(daemon: Daemon) -> None:
    assert daemon.send('rib show in') == ['done']
    assert daemon.send('rib show out') == ['done']


@pytest.mark.parametrize('command', ['rib show', 'rib show sideways', 'rib show extensive'])
def test_show_needs_a_direction(daemon: Daemon, command: str) -> None:
    assert daemon.send(command) == ['error']


# ===================================================================== flush, clear


def test_flush_out_sends_the_adj_rib_out_again(daemon: Daemon) -> None:
    daemon.send('peer * announce route 10.0.0.0/24 next-hop 1.2.3.4')
    for address in (FIRST, SECOND):
        # as once the routes have been sent
        daemon.neighbor(address).rib.outgoing.reset()
        assert not daemon.neighbor(address).rib.outgoing.pending()

    assert daemon.send('rib flush out') == ['done']
    for address in (FIRST, SECOND):
        assert daemon.neighbor(address).rib.outgoing.pending()
        assert daemon.announced(address) == ['10.0.0.0/24']


def test_clear_out_withdraws_every_route(daemon: Daemon) -> None:
    populate(daemon)
    assert daemon.send('rib clear out') == ['done']
    assert daemon.announced(FIRST) == []
    assert daemon.announced(SECOND) == []


def test_clear_in_forgets_what_was_received(daemon: Daemon) -> None:
    receive(daemon, FIRST, '10.8.0.0/24')
    receive(daemon, SECOND, '10.9.0.0/24')
    assert daemon.send('rib clear in') == ['done']
    assert received(daemon, FIRST) == []
    assert received(daemon, SECOND) == []


def test_clear_in_leaves_the_adj_rib_out(daemon: Daemon) -> None:
    daemon.send('peer * announce route 10.0.0.0/24 next-hop 1.2.3.4')
    daemon.send('rib clear in')
    assert daemon.announced(FIRST) == ['10.0.0.0/24']


def test_api_4_flush_and_clear(text_daemon: Daemon) -> None:
    populate(text_daemon, api_4=True)
    assert text_daemon.send('flush adj-rib out') == ['done']
    assert text_daemon.send('clear adj-rib out') == ['done']
    assert text_daemon.announced(FIRST) == []
    assert text_daemon.send('clear adj-rib in') == ['done']


def test_flush_and_clear_with_no_peer_are_refused() -> None:
    daemon = Daemon(
        """
        process helper { run /usr/bin/true; encoder json; }
        neighbor 127.0.0.1 { router-id 10.0.0.1; local-address 127.0.0.100; local-as 65000; peer-as 65001; }
        """
    )
    try:
        # the helper is not one of the neighbor's processes, so it has no peer
        assert daemon.send('rib flush out') == ['error']
        assert daemon.send('rib clear out') == ['error']
    finally:
        daemon.close()
