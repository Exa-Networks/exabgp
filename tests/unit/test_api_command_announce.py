"""The announce and withdraw commands: what each takes, refuses, and does to the RIB.

    peer <selector> announce route | ipv4 | ipv6 | flow | vpls | attributes ...
    peer <selector> withdraw route | ipv4 | ipv6 | flow | vpls | attributes ...
    peer <selector> announce eor | route-refresh | operational ...

and the API 4 forms of the same, `announce ...` and `neighbor <ip> announce ...`. Each runs
on a real Reactor (tests/api_daemon.py): a route taken is in the outgoing RIB of the
neighbors the selector names and carry its family, and nowhere else.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from exabgp.bgp.message.open.capability.refresh import REFRESH
from exabgp.protocol.family import AFI, SAFI
from tests.api_daemon import Daemon, FIRST, HELPER, SECOND, failed

IPV4_UNICAST = (AFI.ipv4, SAFI.unicast)


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


# ============================================================================ routes


def test_a_route_is_announced_to_every_peer_of_the_selector(daemon: Daemon) -> None:
    assert daemon.send('peer * announce route 10.0.0.0/24 next-hop 1.2.3.4') == ['done']
    assert daemon.announced(FIRST) == ['10.0.0.0/24']
    assert daemon.announced(SECOND) == ['10.0.0.0/24']


def test_a_route_is_announced_to_the_peer_named_only(daemon: Daemon) -> None:
    assert daemon.send(f'peer {SECOND} announce route 10.0.0.0/24 next-hop 1.2.3.4') == ['done']
    assert daemon.announced(FIRST) == []
    assert daemon.announced(SECOND) == ['10.0.0.0/24']


def test_the_route_keeps_what_the_command_said(daemon: Daemon) -> None:
    daemon.send(f'peer {FIRST} announce route 10.0.0.0/24 next-hop 1.2.3.4 med 20 community [65000:1]')
    (route,) = daemon.neighbor(FIRST).rib.outgoing.cached_routes(None)
    assert route.extensive() == '10.0.0.0/24 next-hop 1.2.3.4 med 20 community 65000:1'


def test_the_helper_announcing_a_route_owns_it(daemon: Daemon) -> None:
    # its routes are withdrawn when it exits (issue #304)
    daemon.send(f'peer {FIRST} announce route 10.0.0.0/24 next-hop 1.2.3.4')
    assert [str(route.nlri) for route in daemon.neighbor(FIRST).rib.outgoing.owned(HELPER)] == ['10.0.0.0/24']


def test_a_route_is_only_given_to_the_neighbors_with_its_family(daemon: Daemon) -> None:
    assert daemon.send('peer * announce route 2001:db8::/32 next-hop 2001:db8::1') == ['done']
    assert daemon.announced(FIRST) == ['2001:db8::/32']
    assert daemon.announced(SECOND) == []


def test_a_withdrawn_route_leaves_the_rib(daemon: Daemon) -> None:
    daemon.send('peer * announce route 10.0.0.0/24 next-hop 1.2.3.4')
    daemon.send('peer * announce route 10.0.1.0/24 next-hop 1.2.3.4')
    assert daemon.send(f'peer {FIRST} withdraw route 10.0.0.0/24') == ['done']
    assert daemon.announced(FIRST) == ['10.0.1.0/24']
    assert daemon.announced(SECOND) == ['10.0.0.0/24', '10.0.1.0/24']


@pytest.mark.parametrize('keywords', ['sync', 'async', 'json', 'sync json', 'json async'])
def test_the_trailing_sync_and_encoding_keywords_are_not_part_of_the_route(daemon: Daemon, keywords: str) -> None:
    # sync waits for the routes to be sent to the peers which have a session: none here
    assert daemon.send(f'peer {FIRST} announce route 10.0.0.0/24 next-hop 1.2.3.4 {keywords}') == ['done']
    (route,) = daemon.neighbor(FIRST).rib.outgoing.cached_routes(None)
    assert route.extensive() == '10.0.0.0/24 next-hop 1.2.3.4'


@pytest.mark.parametrize(
    ('command', 'reason'),
    [
        ('peer * announce route 10.0.0.0/24', 'announce requires nexthop: 10.0.0.0/24'),
        ('peer * announce route', 'Could not parse route: route'),
        ('peer * withdraw route', 'Could not parse route: route'),
        ('peer * announce route 10.0.0.0/24 next-hop 1.2.3.4 rd 100:100', None),
        ('peer * announce bogus 10.0.0.0/24', 'unknown announce type: bogus'),
        ('peer * withdraw bogus 10.0.0.0/24', 'unknown withdraw type: bogus'),
    ],
)
def test_a_route_which_can_not_be_sent_is_refused_and_nothing_is_announced(
    daemon: Daemon, command: str, reason: str | None
) -> None:
    lines = daemon.send(command)
    assert lines[-1] == 'error'
    if reason is not None:
        assert lines == [failed(reason), 'error']
    assert daemon.announced(FIRST) == []
    assert daemon.announced(SECOND) == []


def test_announce_with_nothing_to_announce_is_refused(daemon: Daemon) -> None:
    assert daemon.send('peer * announce') == ['error']
    assert daemon.send('peer * withdraw') == ['error']


# ===================================================================== by family name


def test_ipv4_and_ipv6_announce_and_withdraw(daemon: Daemon) -> None:
    assert daemon.send('peer * announce ipv4 unicast 10.0.0.0/24 next-hop 1.2.3.4') == ['done']
    assert daemon.send('peer * announce ipv6 unicast 2001:db8::/32 next-hop 2001:db8::1') == ['done']
    assert daemon.send('peer * announce ipv4 mpls-vpn 10.1.0.0/24 next-hop 1.2.3.4 rd 100:100 label 10') == ['done']
    assert daemon.announced(FIRST) == ['10.0.0.0/24', '10.1.0.0/24 label 10 (161) rd 100:100', '2001:db8::/32']
    assert daemon.announced(SECOND) == ['10.0.0.0/24']

    assert daemon.send('peer * withdraw ipv4 unicast 10.0.0.0/24') == ['done']
    assert daemon.send('peer * withdraw ipv6 unicast 2001:db8::/32') == ['done']
    assert daemon.announced(FIRST) == ['10.1.0.0/24 label 10 (161) rd 100:100']
    assert daemon.announced(SECOND) == []


@pytest.mark.parametrize(
    'command',
    [
        'peer * announce ipv4 unicast nonsense',
        'peer * announce ipv6 unicast nonsense',
        'peer * withdraw ipv4 unicast nonsense',
        'peer * withdraw ipv6 unicast nonsense',
        # a VPN route with no label can not be packed
        'peer * announce ipv4 mpls-vpn 10.0.0.0/24 next-hop 1.2.3.4 rd 100:100',
    ],
)
def test_ipv4_and_ipv6_refuse_what_they_can_not_parse(daemon: Daemon, command: str) -> None:
    assert daemon.send(command)[-1] == 'error'
    assert daemon.announced(FIRST) == []


def test_flow_announce_and_withdraw(daemon: Daemon) -> None:
    assert daemon.send('peer * announce flow route destination 10.0.0.0/24 discard') == ['done']
    # only the first neighbor carries ipv4 flow
    assert daemon.announced(FIRST) == ['flow destination-ipv4 10.0.0.0/24']
    assert daemon.announced(SECOND) == []
    assert daemon.send('peer * withdraw flow route destination 10.0.0.0/24 discard') == ['done']
    assert daemon.announced(FIRST) == []


@pytest.mark.parametrize('command', ['peer * announce flow route garbage', 'peer * withdraw flow route garbage'])
def test_flow_refuses_what_it_can_not_parse(daemon: Daemon, command: str) -> None:
    assert daemon.send(command) == ['error']


@pytest.mark.parametrize(
    'command',
    [
        'peer * announce flow route',
        'peer * announce flow route discard',
        'peer * announce flow route rate-limit 9600',
        'peer * announce ipv4 flow discard',
    ],
)
def test_a_flow_route_without_a_match_is_refused(daemon: Daemon, command: str) -> None:
    """A flow route with no match component matches every packet: 4.2 and 5.0 sent it."""
    assert daemon.send(command) == ['error']
    assert daemon.announced(FIRST) == []


VPLS = 'vpls endpoint 10 offset 20 size 8 base 203 rd 1:1'


def test_vpls_announce_and_withdraw(daemon: Daemon) -> None:
    assert daemon.send(f'peer * announce {VPLS} next-hop 1.2.3.4') == ['done']
    assert daemon.announced(FIRST) == ['vpls rd 1:1 endpoint 10 base 203 offset 20 size 8']
    assert daemon.announced(SECOND) == []
    assert daemon.send(f'peer * withdraw {VPLS}') == ['done']
    assert daemon.announced(FIRST) == []


@pytest.mark.parametrize('command', ['peer * announce vpls garbage', 'peer * withdraw vpls garbage'])
def test_vpls_refuses_what_it_can_not_parse(daemon: Daemon, command: str) -> None:
    assert daemon.send(command) == ['error']


def test_attributes_announce_every_nlri_and_withdraw_them(daemon: Daemon) -> None:
    assert daemon.send('peer * announce attributes next-hop 1.2.3.4 med 5 nlri 10.1.0.0/24 10.2.0.0/24') == ['done']
    assert daemon.announced(FIRST) == ['10.1.0.0/24', '10.2.0.0/24']
    assert daemon.announced(SECOND) == ['10.1.0.0/24', '10.2.0.0/24']
    assert daemon.send('peer * withdraw attribute next-hop 1.2.3.4 nlri 10.1.0.0/24') == ['done']
    assert daemon.announced(FIRST) == ['10.2.0.0/24']


@pytest.mark.parametrize(
    'command',
    [
        'peer * announce attributes nonsense',
        'peer * withdraw attributes nonsense',
        # a VPN route with no label can not be packed
        'peer * announce attributes next-hop 1.2.3.4 rd 100:100 nlri 10.0.0.0/24',
    ],
)
def test_attributes_refuse_what_can_not_be_sent(daemon: Daemon, command: str) -> None:
    assert daemon.send(command)[-1] == 'error'
    assert daemon.announced(FIRST) == []


# ====================================================== messages which are not routes


def test_eor_is_queued_for_the_established_peers(daemon: Daemon) -> None:
    daemon.establish(FIRST)
    assert daemon.send('peer * announce eor ipv6 unicast') == ['done']
    assert [str(family) for family in daemon.neighbor(FIRST).eor] == ['ipv6 unicast']
    # the session of the other is not up, so it is not sent one
    assert list(daemon.neighbor(SECOND).eor) == []


def test_eor_with_no_family_is_ipv4_unicast(daemon: Daemon) -> None:
    daemon.establish()
    assert daemon.send(f'peer {SECOND} announce eor') == ['done']
    assert [str(family) for family in daemon.neighbor(SECOND).eor] == ['ipv4 unicast']


def test_eor_with_no_established_peer_is_refused(daemon: Daemon) -> None:
    assert daemon.send('peer * announce eor ipv4 unicast') == ['error']


@pytest.mark.parametrize('family', ['ipv4', 'ipv4 bogus', 'bogus unicast', 'ipv4 unicast extra'])
def test_eor_for_no_family_is_refused(daemon: Daemon, family: str) -> None:
    daemon.establish()
    assert daemon.send(f'peer * announce eor {family}') == ['error']
    assert list(daemon.neighbor(FIRST).eor) == []


def test_route_refresh_is_queued_for_the_established_peers(daemon: Daemon) -> None:
    daemon.establish(SECOND)
    daemon.negotiate(SECOND, REFRESH.NORMAL, [IPV4_UNICAST])
    assert daemon.send('peer * announce route-refresh ipv4 unicast') == ['done']
    (refresh,) = daemon.neighbor(SECOND).refresh
    assert (str(refresh.afi), str(refresh.safi)) == ('ipv4', 'unicast')
    assert list(daemon.neighbor(FIRST).refresh) == []


# ================================================== a family no selected peer carries
#
# 4.x and 5.x answered done and sent nothing; the helper was told it worked.


@pytest.mark.parametrize(
    'command',
    [
        f'peer {SECOND} announce route 2001:db8::/32 next-hop 2001:db8::1',
        f'peer {SECOND} announce flow route destination 10.0.0.0/24 discard',
        f'peer {SECOND} announce ipv6 unicast 2001:db8::/32 next-hop 2001:db8::1',
        f'peer {SECOND} group announce route 2001:db8::/32 next-hop 2001:db8::1',
    ],
)
def test_a_route_for_a_family_no_selected_peer_carries_is_refused(daemon: Daemon, command: str) -> None:
    assert daemon.send(command)[-1] == 'error'
    assert daemon.announced(SECOND) == []


def test_a_route_for_a_family_one_selected_peer_carries_is_sent_to_it(daemon: Daemon) -> None:
    assert daemon.send('peer * announce route 2001:db8::/32 next-hop 2001:db8::1') == ['done']
    assert daemon.announced(FIRST) == ['2001:db8::/32']
    assert daemon.announced(SECOND) == []


def test_an_eor_for_a_family_no_established_peer_carries_is_refused(daemon: Daemon) -> None:
    daemon.establish(SECOND)
    assert daemon.send(f'peer {SECOND} announce eor ipv6 unicast') == ['error']
    assert list(daemon.neighbor(SECOND).eor) == []


def test_a_route_refresh_for_a_family_no_established_peer_carries_is_refused(daemon: Daemon) -> None:
    daemon.establish(SECOND)
    assert daemon.send(f'peer {SECOND} announce route-refresh ipv6 unicast') == ['error']
    assert list(daemon.neighbor(SECOND).refresh) == []


def test_route_refresh_with_no_established_peer_is_refused(daemon: Daemon) -> None:
    assert daemon.send('peer * announce route-refresh ipv4 unicast') == ['error']


@pytest.mark.parametrize('family', ['', 'ipv4', 'ipv9 unicast', 'ipv4 unicast extra'])
def test_route_refresh_for_no_family_is_refused(daemon: Daemon, family: str) -> None:
    daemon.establish()
    assert daemon.send(f'peer * announce route-refresh {family}') == ['error']
    assert list(daemon.neighbor(FIRST).refresh) == []


def test_an_operational_message_is_queued_for_the_peers(daemon: Daemon) -> None:
    assert daemon.send(f'peer {FIRST} announce operational asm afi ipv4 safi unicast advisory "hello"') == ['done']
    (message,) = daemon.neighbor(FIRST).messages
    assert message.NAME == 'ASM'
    assert list(daemon.neighbor(SECOND).messages) == []


# ===================================================================== the API 4 forms


def test_api_4_announce_and_withdraw_go_to_every_peer(text_daemon: Daemon) -> None:
    assert text_daemon.send('announce route 10.0.0.0/24 next-hop 1.2.3.4') == ['done']
    assert text_daemon.announced(FIRST) == ['10.0.0.0/24']
    assert text_daemon.announced(SECOND) == ['10.0.0.0/24']
    assert text_daemon.send('withdraw route 10.0.0.0/24') == ['done']
    assert text_daemon.announced(SECOND) == []


def test_api_4_neighbor_names_the_peer(text_daemon: Daemon) -> None:
    assert text_daemon.send(f'neighbor {SECOND} announce route 10.0.0.0/24 next-hop 1.2.3.4') == ['done']
    assert text_daemon.announced(FIRST) == []
    assert text_daemon.announced(SECOND) == ['10.0.0.0/24']
    assert text_daemon.send(f'neighbor {SECOND} withdraw route 10.0.0.0/24') == ['done']
    assert text_daemon.announced(SECOND) == []


@pytest.mark.parametrize(
    'command',
    [
        'announce flow route { match { destination 10.0.0.0/24; } then { discard; } }',
        f'announce {VPLS} next-hop 1.2.3.4',
        'announce attribute next-hop 1.2.3.4 nlri 10.9.0.0/24',
        'announce ipv4 unicast 10.8.0.0/24 next-hop 1.1.1.1',
        'announce ipv6 unicast 2001:db8::/32 next-hop 2001:db8::1',
    ],
)
def test_api_4_announces_each_kind_of_route(text_daemon: Daemon, command: str) -> None:
    assert text_daemon.send(command) == ['done']
    assert len(text_daemon.announced(FIRST)) == 1


def test_api_4_neighbor_matching_no_peer_is_refused(text_daemon: Daemon) -> None:
    assert text_daemon.send('neighbor 192.0.2.1 announce route 10.0.0.0/24 next-hop 1.2.3.4') == ['error']


def test_api_4_eor_and_operational(text_daemon: Daemon) -> None:
    text_daemon.establish(FIRST)
    assert text_daemon.send('announce eor ipv4 unicast') == ['done']
    assert [str(family) for family in text_daemon.neighbor(FIRST).eor] == ['ipv4 unicast']
    assert text_daemon.send('announce operational adm afi ipv4 safi unicast advisory "x"') == ['done']
    assert [message.NAME for message in text_daemon.neighbor(FIRST).messages] == ['ADM']


@pytest.mark.parametrize(
    'selector',
    [
        '192.0.2.1',
        '[192.0.2.1]',
        # the address is right, the AS is not
        f'{FIRST} peer-as 1',
    ],
)
def test_a_selector_matching_no_peer_is_refused(daemon: Daemon, selector: str) -> None:
    """It was taken as no selector, and the command went to every peer of the helper."""
    assert daemon.send(f'peer {selector} announce route 10.0.0.0/24 next-hop 1.2.3.4') == ['error']
    assert daemon.announced(FIRST) == []
    assert daemon.announced(SECOND) == []


def test_a_teardown_for_no_peer_tears_none_down(daemon: Daemon) -> None:
    daemon.establish()
    assert daemon.send('peer 192.0.2.1 teardown') == ['error']
    assert daemon.peer(FIRST)._teardown is None
    assert daemon.peer(SECOND)._teardown is None


@pytest.mark.parametrize('kind', ['foo', ''])
def test_an_operational_message_of_no_known_kind_is_refused(daemon: Daemon, kind: str) -> None:
    """It was answered done, and nothing was sent."""
    assert daemon.send(f'peer {FIRST} announce operational {kind}'.strip())[-1] == 'error'
    assert list(daemon.neighbor(FIRST).messages) == []


def test_an_operational_message_which_does_not_parse_is_refused(daemon: Daemon) -> None:
    """The parser's ValueError went up to the reactor, which is what answered the error."""
    assert daemon.send(f'peer {FIRST} announce operational asm afi ipv4')[-1] == 'error'
    assert list(daemon.neighbor(FIRST).messages) == []


def test_api_4_neighbor_operational_is_queued_for_the_peer(text_daemon: Daemon) -> None:
    """`neighbor <ip> announce operational` read its kind one word too early: done, and nothing sent."""
    command = f'neighbor {FIRST} announce operational adm afi ipv4 safi unicast advisory "x"'
    assert text_daemon.send(command) == ['done']
    assert [message.NAME for message in text_daemon.neighbor(FIRST).messages] == ['ADM']


def test_api_4_operational_of_no_known_kind_is_refused(text_daemon: Daemon) -> None:
    assert text_daemon.send('announce operational foo') == [
        'error: unknown operational message: operational foo',
        'error',
    ]
    assert text_daemon.send(f'neighbor {FIRST} announce operational')[-1] == 'error'
