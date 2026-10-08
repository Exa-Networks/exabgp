"""RFC 4271 5.1.2 and 5.1.3: the AS_PATH and the NEXT_HOP of a route we originate.

5.1.3 forbids advertising a route to a peer with an address of that peer as NEXT_HOP:
nothing compared the next hop with the peer address, so the configuration and the API
both sent it. It is now refused by the configuration, refused by the API when no selected
peer can take it, and skipped for the one peer it names when others can.

5.1.2 has the originating speaker put its own AS first in the AS_PATH sent to an external
peer. exabgp sends a configured AS_PATH as written, on purpose: route servers, route
injectors and the functional tests rely on it. That is recorded as a gap in the ledger,
and the operator is warned, by the configuration and by the API, when the path does not
start with the AS the peer sees us as.
"""

from __future__ import annotations

from typing import Iterator
from unittest.mock import Mock, patch

import pytest

from exabgp.configuration.configuration import Configuration

from tests.api_daemon import FIRST, SECOND, Daemon


def configured(
    peer: str, family: str, static: str, local_as: int = 65001, extra: str = ''
) -> tuple[bool, Configuration]:
    local = '2001:db8::2' if ':' in peer else '192.0.2.2'
    configuration = Configuration(
        [
            f'neighbor {peer} {{ router-id 192.0.2.2; local-address {local}; local-as {local_as}; peer-as 65002; '
            f'{extra} family {{ {family} }} static {{ {static} }} }}'
        ],
        text=True,
    )
    return configuration.reload(), configuration


# ============================================================== 5.1.3 NEXT_HOP of the peer


@pytest.mark.rfc('rfc4271#5.1.3-no-next-hop-of-the-peer', polarity='negative')
@pytest.mark.parametrize(
    ('peer', 'family', 'static'),
    [
        ('192.0.2.1', 'ipv4 unicast;', 'route 10.0.0.0/24 next-hop 192.0.2.1;'),
        ('2001:db8::1', 'ipv6 unicast;', 'route 2001:db8:1::/48 next-hop 2001:db8::1;'),
        ('192.0.2.1', 'ipv4 mpls-vpn;', 'route 10.0.0.0/24 rd 65000:1 label 100 next-hop 192.0.2.1;'),
        ('2001:db8::1', 'ipv6 mpls-vpn;', 'route 2001:db8:1::/48 rd 65000:1 label 100 next-hop 2001:db8::1;'),
        # an IPv4 peer, reached through the IPv4-mapped form of its address
        ('192.0.2.1', 'ipv6 unicast;', 'route 2001:db8:1::/48 next-hop ::ffff:192.0.2.1;'),
    ],
)
def test_the_configuration_refuses_a_next_hop_of_the_peer(peer: str, family: str, static: str) -> None:
    loaded, configuration = configured(peer, family, static)
    assert not loaded
    assert 'is an address of the peer' in str(configuration.error), configuration.error


@pytest.mark.rfc('rfc4271#5.1.3-no-next-hop-of-the-peer')
@pytest.mark.parametrize(
    ('peer', 'family', 'static'),
    [
        ('192.0.2.1', 'ipv4 unicast;', 'route 10.0.0.0/24 next-hop 192.0.2.9;'),
        ('192.0.2.1', 'ipv4 unicast;', 'route 10.0.0.0/24 next-hop self;'),
        ('2001:db8::1', 'ipv6 unicast;', 'route 2001:db8:1::/48 next-hop 2001:db8::9;'),
        ('192.0.2.1', 'ipv4 mpls-vpn;', 'route 10.0.0.0/24 rd 65000:1 label 100 next-hop 192.0.2.9;'),
    ],
)
def test_the_configuration_accepts_any_other_next_hop(peer: str, family: str, static: str) -> None:
    loaded, configuration = configured(peer, family, static)
    assert loaded, configuration.error
    (neighbor,) = configuration.neighbors.values()
    assert len(neighbor.routes) == 1


@pytest.fixture
def daemon() -> Iterator[Daemon]:
    created = Daemon()
    yield created
    created.close()


@pytest.mark.rfc('rfc4271#5.1.3-no-next-hop-of-the-peer', polarity='negative')
def test_the_api_refuses_a_route_whose_next_hop_is_the_only_selected_peer(daemon: Daemon) -> None:
    lines = daemon.send(f'neighbor {SECOND} announce route 10.0.0.0/24 next-hop {SECOND}')
    assert lines[-1] == 'error', lines
    assert daemon.announced(SECOND) == []


@pytest.mark.rfc('rfc4271#5.1.3-no-next-hop-of-the-peer', polarity='negative')
def test_the_api_sends_it_to_the_other_peers_but_not_the_one_it_names(daemon: Daemon) -> None:
    """Steering one peer's traffic towards another is a use of exabgp: the others get it."""
    lines = daemon.send(f'announce route 10.0.0.0/24 next-hop {SECOND}')
    assert lines[-1] == 'done', lines
    assert daemon.announced(FIRST) == ['10.0.0.0/24']
    assert daemon.announced(SECOND) == []


@pytest.mark.rfc('rfc4271#5.1.3-no-next-hop-of-the-peer')
def test_the_api_sends_a_route_with_another_next_hop_to_every_peer(daemon: Daemon) -> None:
    lines = daemon.send('announce route 10.0.0.0/24 next-hop 192.0.2.9')
    assert lines[-1] == 'done', lines
    assert daemon.announced(FIRST) == ['10.0.0.0/24']
    assert daemon.announced(SECOND) == ['10.0.0.0/24']


# ======================================================= 5.1.2 our AS first, to an external peer


def warned(module: str, run: object) -> list[str]:
    """The warnings `module` logs while `run` runs."""
    with patch(f'{module}.log') as logged:
        logged.warning = Mock()
        assert callable(run)
        run()
    # what is logged is a lazymsg, a callable making the text only when a log wants it
    return [str(call.args[0]()) for call in logged.warning.call_args_list]


CONFIGURATION_MODULE = 'exabgp.configuration.grammar.tree.neighbor'


@pytest.mark.parametrize(
    'as_path',
    ['as-path [];', 'as-path [ 65009 3 ];', 'as-path ( 65001 3 );', 'as-path confed-sequence [ 65001 ] [ 3 ];'],
)
def test_the_configuration_warns_of_an_as_path_not_starting_with_our_as(as_path: str) -> None:
    messages = warned(
        CONFIGURATION_MODULE,
        lambda: configured('192.0.2.1', 'ipv4 unicast;', f'route 10.0.0.0/24 next-hop 192.0.2.9 {as_path}'),
    )
    assert any('as-path' in message for message in messages), messages


@pytest.mark.parametrize(
    ('static', 'local_as'),
    [
        ('route 10.0.0.0/24 next-hop 192.0.2.9 as-path [ 65001 3 ];', 65001),
        # with no AS_PATH, exabgp sends our AS itself
        ('route 10.0.0.0/24 next-hop 192.0.2.9;', 65001),
        # an internal peer is sent the path as written, which RFC 4271 5.1.2 b) wants
        ('route 10.0.0.0/24 next-hop 192.0.2.9 as-path [ 65009 3 ];', 65002),
    ],
)
def test_the_configuration_is_silent_when_our_as_is_first_or_the_peer_is_internal(static: str, local_as: int) -> None:
    messages = warned(CONFIGURATION_MODULE, lambda: configured('192.0.2.1', 'ipv4 unicast;', static, local_as))
    assert not any('as-path' in message for message in messages), messages


def test_outside_the_confederation_our_as_is_the_confederation_identifier() -> None:
    confederation = 'confederation { identifier 100; members [ 65001 65011 ]; }'
    first = 'route 10.0.0.0/24 next-hop 192.0.2.9 as-path [ 100 3 ];'
    messages = warned(
        CONFIGURATION_MODULE, lambda: configured('192.0.2.1', 'ipv4 unicast;', first, extra=confederation)
    )
    assert not any('as-path' in message for message in messages), messages
    member = 'route 10.0.0.0/24 next-hop 192.0.2.9 as-path [ 65001 3 ];'
    messages = warned(
        CONFIGURATION_MODULE, lambda: configured('192.0.2.1', 'ipv4 unicast;', member, extra=confederation)
    )
    assert any('as-path' in message for message in messages), messages


def test_the_api_warns_of_an_as_path_not_starting_with_our_as(daemon: Daemon) -> None:
    messages = warned(
        'exabgp.configuration.configuration',
        lambda: daemon.send(f'neighbor {SECOND} announce route 10.0.0.0/24 next-hop 192.0.2.9 as-path [ 65009 3 ]'),
    )
    assert any('as-path' in message for message in messages), messages
    assert daemon.announced(SECOND) == ['10.0.0.0/24']


def test_the_api_is_silent_when_our_as_is_first(daemon: Daemon) -> None:
    messages = warned(
        'exabgp.configuration.configuration',
        lambda: daemon.send(f'neighbor {SECOND} announce route 10.0.0.0/24 next-hop 192.0.2.9 as-path [ 65000 3 ]'),
    )
    assert not any('as-path' in message for message in messages), messages


@pytest.mark.rfc('rfc4271#5.1.2-originator-as-first-to-an-external-peer')
@pytest.mark.xfail(strict=True, reason='a configured AS_PATH is sent as written, see the ledger note')
def test_a_configured_as_path_to_an_external_peer_is_sent_with_our_as_first() -> None:
    from exabgp.bgp.message.update.attribute import Attribute

    loaded, configuration = configured(
        '192.0.2.1', 'ipv4 unicast;', 'route 10.0.0.0/24 next-hop 192.0.2.9 as-path [ 65009 ];'
    )
    assert loaded, configuration.error
    (neighbor,) = configuration.neighbors.values()
    (route,) = neighbor.routes
    as_path = route.attributes[Attribute.CODE.AS_PATH]
    # what would be sent, were our AS prepended: 65001 65009
    assert [int(asn) for asn in as_path.as_seq()] == [65001, 65009]
