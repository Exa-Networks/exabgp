"""The routes commands: routes by index.

    peer <selector> routes [<afi> [<safi>]] list
    peer <selector> routes add <route>
    peer <selector> routes remove <route>
    peer <selector> routes remove index <hex>

Each runs on a real Reactor (tests/api_daemon.py) with two neighbors, of which only the first
carries ipv6. The answer is JSON, and like every other answer it ends with done, or with
error when the command did not do what it was asked.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.api_daemon import FIRST, HELPER, SECOND, Daemon, answer


@pytest.fixture
def daemon() -> Iterator[Daemon]:
    created = Daemon()
    yield created
    created.close()


def index(daemon: Daemon, address: str, prefix: str) -> str:
    """The index of a route the outgoing RIB of a neighbor holds, as the API writes it."""
    for route in daemon.neighbor(address).rib.outgoing.cached_routes(None):
        if str(route.nlri) == prefix:
            return route.index().hex()
    raise AssertionError(f'{prefix} is not in the RIB of {address}')


# ============================================================================== list


def test_list_of_nothing(daemon: Daemon) -> None:
    assert daemon.send('peer * routes list') == ['[]', 'done']


def test_list_gives_each_route_of_each_neighbor_with_its_index(daemon: Daemon) -> None:
    daemon.send('peer * announce route 10.0.0.0/24 next-hop 1.2.3.4')
    daemon.send(f'peer {FIRST} announce route 2001:db8::/32 next-hop 2001:db8::1')
    lines = daemon.send('peer * routes list')
    (listed,) = answer(lines)
    assert sorted(listed, key=lambda entry: (entry['neighbor'], entry['route'])) == [
        {
            'index': index(daemon, FIRST, '10.0.0.0/24'),
            'route': '10.0.0.0/24 next-hop 1.2.3.4',
            'neighbor': daemon.key(FIRST),
        },
        {
            'index': index(daemon, FIRST, '2001:db8::/32'),
            'route': '2001:db8::/32 next-hop 2001:db8::1',
            'neighbor': daemon.key(FIRST),
        },
        {
            'index': index(daemon, SECOND, '10.0.0.0/24'),
            'route': '10.0.0.0/24 next-hop 1.2.3.4',
            'neighbor': daemon.key(SECOND),
        },
    ]
    assert lines[-1] == 'done'


def test_list_of_the_neighbor_named(daemon: Daemon) -> None:
    daemon.send('peer * announce route 10.0.0.0/24 next-hop 1.2.3.4')
    ((listed,),) = answer(daemon.send(f'peer {SECOND} routes list'))
    assert listed['neighbor'] == daemon.key(SECOND)


@pytest.mark.parametrize(
    ('family', 'routes'),
    [
        ('ipv6', ['2001:db8::/32 next-hop 2001:db8::1']),
        ('ipv4', ['10.0.0.0/24 next-hop 1.2.3.4']),
        ('ipv4 unicast', ['10.0.0.0/24 next-hop 1.2.3.4']),
        ('ipv4 flow', []),
    ],
)
def test_list_of_one_family(daemon: Daemon, family: str, routes: list[str]) -> None:
    daemon.send(f'peer {FIRST} announce route 10.0.0.0/24 next-hop 1.2.3.4')
    daemon.send(f'peer {FIRST} announce route 2001:db8::/32 next-hop 2001:db8::1')
    (listed,) = answer(daemon.send(f'peer {FIRST} routes {family} list'))
    assert [entry['route'] for entry in listed] == routes


# =============================================================================== add


def test_add_announces_the_route_and_answers_its_index(daemon: Daemon) -> None:
    lines = daemon.send(f'peer {SECOND} routes add route 10.0.0.0/24 next-hop 1.2.3.4')
    assert answer(lines) == [
        {'index': index(daemon, SECOND, '10.0.0.0/24'), 'route': '10.0.0.0/24 next-hop 1.2.3.4', 'success': True}
    ]
    assert lines[-1] == 'done'
    assert daemon.announced(SECOND) == ['10.0.0.0/24']
    assert daemon.announced(FIRST) == []
    # owned by the helper, so withdrawn when it exits
    assert [str(route.nlri) for route in daemon.neighbor(SECOND).rib.outgoing.owned(HELPER)] == ['10.0.0.0/24']


def test_add_of_several_routes_answers_each(daemon: Daemon) -> None:
    lines = daemon.send('peer * routes add attributes next-hop 1.2.3.4 nlri 10.7.0.0/24 10.8.0.0/24')
    (added,) = answer(lines)
    assert [(entry['route'], entry['success']) for entry in added] == [
        ('10.7.0.0/24 next-hop 1.2.3.4', True),
        ('10.8.0.0/24 next-hop 1.2.3.4', True),
    ]
    assert lines[-1] == 'done'
    assert daemon.announced(SECOND) == ['10.7.0.0/24', '10.8.0.0/24']


def test_add_of_a_route_which_can_not_be_sent_says_why(daemon: Daemon) -> None:
    lines = daemon.send('peer * routes add route 10.0.0.0/24')
    assert answer(lines) == [
        {'route': '10.0.0.0/24', 'success': False, 'error': 'announce requires nexthop: 10.0.0.0/24'}
    ]
    assert lines[-1] == 'error'
    assert daemon.announced(FIRST) == []


def test_add_of_a_route_no_neighbor_named_carries(daemon: Daemon) -> None:
    lines = daemon.send(f'peer {SECOND} routes add route 2001:db8::/32 next-hop 2001:db8::1')
    ((added,),) = [answer(lines)]
    assert added['success'] is False
    assert lines[-1] == 'error'
    assert daemon.announced(SECOND) == []


@pytest.mark.parametrize(
    ('command', 'reason'),
    [
        ('peer * routes add', 'routes add requires route specification'),
        ('peer * routes add garbage', 'Could not parse route: garbage'),
    ],
)
def test_add_refuses_what_is_not_a_route(daemon: Daemon, command: str, reason: str) -> None:
    assert daemon.send(command) == [f'error: {reason}', 'error']
    assert daemon.announced(FIRST) == []


# ============================================================================ remove


def test_remove_by_route(daemon: Daemon) -> None:
    daemon.send('peer * routes add route 10.0.0.0/24 next-hop 1.2.3.4')
    removed = index(daemon, FIRST, '10.0.0.0/24')
    lines = daemon.send(f'peer {FIRST} routes remove route 10.0.0.0/24')
    assert answer(lines) == [{'removed': True, 'route': '10.0.0.0/24', 'index': removed}]
    assert lines[-1] == 'done'
    assert daemon.announced(FIRST) == []
    assert daemon.announced(SECOND) == ['10.0.0.0/24']


def test_remove_by_index(daemon: Daemon) -> None:
    (added,) = answer(daemon.send('peer * routes add route 10.0.0.0/24 next-hop 1.2.3.4'))
    lines = daemon.send(f'peer * routes remove index {added["index"]}')
    assert answer(lines) == [{'removed': True, 'index': added['index']}]
    assert lines[-1] == 'done'
    assert daemon.announced(FIRST) == []
    assert daemon.announced(SECOND) == []


def test_remove_of_an_index_which_is_not_there(daemon: Daemon) -> None:
    (added,) = answer(daemon.send('peer * routes add route 10.0.0.0/24 next-hop 1.2.3.4'))
    daemon.send(f'peer * routes remove index {added["index"]}')
    lines = daemon.send(f'peer * routes remove index {added["index"]}')
    assert answer(lines) == [{'removed': False, 'index': added['index']}]
    assert lines[-1] == 'error'


@pytest.mark.parametrize(
    ('command', 'reason'),
    [
        ('peer * routes remove', 'routes remove requires route spec or index'),
        ('peer * routes remove index zz', 'Invalid hex index: zz'),
        ('peer * routes remove garbage', 'Could not parse route: garbage'),
    ],
)
def test_remove_refuses_what_is_not_a_route(daemon: Daemon, command: str, reason: str) -> None:
    daemon.send('peer * routes add route 10.0.0.0/24 next-hop 1.2.3.4')
    assert daemon.send(command) == [f'error: {reason}', 'error']
    assert daemon.announced(FIRST) == ['10.0.0.0/24']


def test_routes_needs_an_action(daemon: Daemon) -> None:
    assert daemon.send('peer * routes') == ['error: routes requires action: list, add, or remove', 'error']
    assert daemon.send('peer * routes ipv4 unicast') == ['error: routes requires action: list, add, or remove', 'error']


def test_with_ack_disabled_the_answer_is_still_given(daemon: Daemon) -> None:
    """Disabling ack drops done and error. It dropped the JSON of the routes commands too,
    which were the only queries a helper with ack disabled could not get an answer to."""
    daemon.send('session ack disable')
    (added,) = answer(daemon.send('peer * routes add route 10.0.0.0/24 next-hop 1.2.3.4'))
    assert added['success'] is True
    assert daemon.send('peer * routes ipv6 list') == ['[]']
