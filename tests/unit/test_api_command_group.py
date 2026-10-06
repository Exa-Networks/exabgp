"""The group commands, which apply several announcements and withdrawals together.

    group start, <commands>, group end
    peer <selector> group <command> ; <command> ; ...

Each runs on a real Reactor (tests/api_daemon.py) with two neighbors. What a group holds is
only in the RIB once the group is applied, and the answer counts what was applied.
tests/unit/test_reactor_api_command_group.py covers the buffer and its limits.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.api_daemon import FIRST, SECOND, Daemon, answer


@pytest.fixture
def daemon() -> Iterator[Daemon]:
    created = Daemon()
    # a helper written for API 6: answered in JSON from its first command
    created.send('session ping')
    yield created
    created.close()


@pytest.fixture
def text_daemon() -> Iterator[Daemon]:
    """A helper written for API 4, configured `encoder text`."""
    created = Daemon(encoder='text')
    created.send('ping text')
    yield created
    created.close()


# ======================================================================== multi line


def test_a_group_is_applied_at_its_end(daemon: Daemon) -> None:
    daemon.send('peer * announce route 10.9.0.0/24 next-hop 1.2.3.4')
    assert answer(daemon.send('group start')) == [{'status': 'group started'}]
    assert daemon.send('announce route 10.1.0.0/24 next-hop 1.2.3.4') == ['done']
    assert daemon.send('withdraw route 10.9.0.0/24') == ['done']
    # nothing is applied before the end
    assert daemon.announced(FIRST) == ['10.9.0.0/24']

    lines = daemon.send('group end')
    assert answer(lines) == [{'status': 'group processed', 'announced': 1, 'withdrawn': 1}]
    assert lines[-1] == 'done'
    assert daemon.announced(FIRST) == ['10.1.0.0/24']
    assert daemon.announced(SECOND) == ['10.1.0.0/24']


def test_an_empty_group(daemon: Daemon) -> None:
    daemon.send('group start')
    assert answer(daemon.send('group end')) == [{'status': 'group ended', 'commands': 0}]


def test_groups_do_not_nest(daemon: Daemon) -> None:
    daemon.send('group start')
    assert daemon.send('group start') == ['{"error": "already in group block (nested groups not allowed)"}', 'error']
    # the group started first is still open
    daemon.send('announce route 10.1.0.0/24 next-hop 1.2.3.4')
    assert answer(daemon.send('group end'))[0]['announced'] == 1


def test_an_api_6_command_in_a_group_waits_for_its_end(daemon: Daemon) -> None:
    """Only a line starting with announce or withdraw was held for the group: the API 6 form,
    `peer <selector> announce ...`, was applied at once, and group end found nothing to do."""
    daemon.send(f'peer {FIRST} announce route 10.9.0.0/24 next-hop 1.2.3.4')
    daemon.send('group start')
    assert daemon.send(f'peer {SECOND} announce route 10.1.0.0/24 next-hop 1.2.3.4') == ['done']
    assert daemon.send(f'peer {FIRST} withdraw route 10.9.0.0/24') == ['done']
    assert daemon.announced(SECOND) == []
    assert daemon.announced(FIRST) == ['10.9.0.0/24']

    assert answer(daemon.send('group end')) == [{'status': 'group processed', 'announced': 1, 'withdrawn': 1}]
    # each command keeps the peers its selector named
    assert daemon.announced(SECOND) == ['10.1.0.0/24']
    assert daemon.announced(FIRST) == []


def test_what_is_not_a_route_is_not_held_by_a_group(daemon: Daemon) -> None:
    daemon.send('group start')
    assert answer(daemon.send('system version'))[0]['application'] == 'exabgp'
    daemon.establish()
    assert daemon.send(f'peer {FIRST} announce eor') == ['done']
    assert [str(family) for family in daemon.neighbor(FIRST).eor] == ['ipv4 unicast']


def test_api_4_inline_group(text_daemon: Daemon) -> None:
    """`group <command> ; <command>` is what `exabgp decode` writes and the reference shows, and
    was refused: only `group start` and `group end` were known with no selector before them."""
    lines = text_daemon.send(
        'group announce route 10.1.0.0/24 next-hop 1.2.3.4 ; announce route 10.2.0.0/24 next-hop 1.2.3.4'
    )
    assert lines == ['group processed: 2 announced, 0 withdrawn', 'done']
    assert text_daemon.announced(FIRST) == ['10.1.0.0/24', '10.2.0.0/24']
    assert text_daemon.announced(SECOND) == ['10.1.0.0/24', '10.2.0.0/24']


def test_an_inline_group_with_no_selector_is_for_every_peer(daemon: Daemon) -> None:
    daemon.send('peer * announce route 10.9.0.0/24 next-hop 1.2.3.4')
    lines = daemon.send('group attributes origin igp local-preference 100 ; withdraw route 10.9.0.0/24')
    assert answer(lines) == [{'status': 'group processed', 'announced': 0, 'withdrawn': 1}]
    assert daemon.announced(FIRST) == []
    assert daemon.announced(SECOND) == []


def test_an_end_with_no_start_is_refused(daemon: Daemon) -> None:
    assert daemon.send('group end') == ['{"error": "not in group block"}', 'error']


def test_api_4_group_in_text(text_daemon: Daemon) -> None:
    assert text_daemon.send('group start') == ['group started', 'done']
    text_daemon.send('announce route 10.1.0.0/24 next-hop 1.2.3.4')
    text_daemon.send('announce route 10.2.0.0/24 next-hop 1.2.3.4')
    assert text_daemon.send('group end') == ['group processed: 2 announced, 0 withdrawn', 'done']
    assert text_daemon.announced(SECOND) == ['10.1.0.0/24', '10.2.0.0/24']


def test_api_4_empty_group_in_text(text_daemon: Daemon) -> None:
    text_daemon.send('group start')
    assert text_daemon.send('group end') == ['group ended (0 commands)', 'done']


# ======================================================================= single line


def test_an_inline_group_applies_each_command_to_the_peers_named(daemon: Daemon) -> None:
    daemon.send('peer * announce route 10.9.0.0/24 next-hop 1.2.3.4')
    lines = daemon.send(f'peer {SECOND} group announce route 10.3.0.0/24 next-hop 1.2.3.4 ; withdraw route 10.9.0.0/24')
    assert answer(lines) == [{'status': 'group processed', 'announced': 1, 'withdrawn': 1}]
    assert lines[-1] == 'done'
    assert daemon.announced(SECOND) == ['10.3.0.0/24']
    assert daemon.announced(FIRST) == ['10.9.0.0/24']


def test_an_inline_group_of_each_kind_of_route(daemon: Daemon) -> None:
    lines = daemon.send(
        f'peer {FIRST} group announce ipv4 unicast 10.1.0.0/24 next-hop 1.2.3.4'
        ' ; announce ipv6 unicast 2001:db8::/32 next-hop 2001:db8::1'
        ' ; announce flow route destination 10.0.0.0/24 discard'
        ' ; announce vpls endpoint 10 offset 20 size 8 base 203 rd 1:1 next-hop 1.2.3.4'
        ' ; announce attributes next-hop 1.2.3.4 nlri 10.2.0.0/24'
    )
    assert answer(lines)[0]['announced'] == 5
    assert len(daemon.announced(FIRST)) == 5


def test_shared_attributes_are_given_to_each_withdrawal(daemon: Daemon) -> None:
    daemon.send(f'peer {FIRST} announce route 10.1.0.0/24 next-hop 1.2.3.4')
    lines = daemon.send(f'peer {FIRST} group attributes origin igp local-preference 100 ; withdraw route 10.1.0.0/24')
    assert answer(lines) == [{'status': 'group processed', 'announced': 0, 'withdrawn': 1}]
    assert daemon.announced(FIRST) == []


def test_shared_attributes_are_given_to_each_announcement(daemon: Daemon) -> None:
    daemon.send(
        f'peer {FIRST} group attributes local-preference 200 ; announce route 10.1.0.0/24 next-hop 1.2.3.4 med 5'
    )
    (route,) = daemon.neighbor(FIRST).rib.outgoing.cached_routes(None)
    assert route.extensive() == '10.1.0.0/24 next-hop 1.2.3.4 med 5 local-preference 200'


@pytest.mark.parametrize('command', ['peer * group', 'peer * group ;', 'peer * group  ;  ; '])
def test_an_empty_inline_group_is_refused(daemon: Daemon, command: str) -> None:
    assert daemon.send(command) == ['{"error": "empty group"}', 'error']


def test_a_group_with_a_command_it_could_not_apply_ends_in_error(daemon: Daemon) -> None:
    """The answer listed the errors and ended with done, which a helper reads as success."""
    lines = daemon.send(
        f'peer {SECOND} group announce route 10.3.0.0/24 next-hop 1.2.3.4 ; announce route 10.4.0.0/24 ; bogus thing'
    )
    assert answer(lines) == [
        {
            'status': 'group processed',
            'announced': 1,
            'withdrawn': 0,
            'errors': ['invalid route: announce requires nexthop: 10.4.0.0/24', 'unknown action in group: bogus'],
        }
    ]
    assert lines[-1] == 'error'
    # what could be applied was
    assert daemon.announced(SECOND) == ['10.3.0.0/24']


def test_api_4_group_with_a_command_it_could_not_apply_ends_in_error(text_daemon: Daemon) -> None:
    text_daemon.send('group start')
    text_daemon.send('announce route 10.1.0.0/24')
    assert text_daemon.send('group end') == ['group processed: 0 announced, 0 withdrawn, 1 errors', 'error']
