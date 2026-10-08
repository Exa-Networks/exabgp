"""decode_to_api_command: the API command which sends an UPDATE again.

Each command here is sent the way the reactor sends it (read by the API parser, put in the
neighbor's outgoing RIB, packed as the UPDATE), then the UPDATE is decoded back to a command,
which must be the command itself. `./qa/bin/test_api_encode --self-check` does the same for
every capture of qa/*.ci, from the wire; these are the paths no capture reaches, and what
each is written as.
"""

from __future__ import annotations

from typing import cast

import pytest

from exabgp.bgp.message import UpdateCollection
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.check import _negotiated
from exabgp.configuration.command import decode_to_api_command
from exabgp.configuration.configuration import Configuration
from exabgp.reactor.api import API
from exabgp.reactor.api.command.group import _parse_routes
from exabgp.reactor.loop import Reactor
from exabgp.rib import RIB

FAMILIES = 'ipv4 unicast; ipv6 unicast; ipv4 mpls-vpn; ipv4 flow; ipv4 flow-vpn; ipv4 rtc; ipv4 sr-policy; l2vpn vpls'
NEIGHBOR = f"""
neighbor 127.0.0.1 {{
    router-id 10.0.0.2; local-address 127.0.0.1; local-as 65000; peer-as 65000;
    family {{ {FAMILIES}; ipv4 mup; ipv4 mcast-vpn; }}
}}
"""


@pytest.fixture
def neighbor(monkeypatch: pytest.MonkeyPatch) -> Neighbor:
    monkeypatch.setattr(RIB, '_cache', {})
    configuration = Configuration([NEIGHBOR], text=True)
    assert configuration.reload(), configuration.error
    found: Neighbor = next(iter(configuration.neighbors.values()))
    return found


def _sent(neighbor: Neighbor, command: str) -> str:
    """The UPDATE the reactor sends for a command, in hex, without its header."""
    api = API(cast(Reactor, None))
    commands = command[len('group ') :].split(' ; ') if command.startswith('group ') else [command]
    for each in commands:
        action, _, rest = each.partition(' ')
        routes = _parse_routes(api, rest, action=action)
        assert routes, f'the API refuses {each!r}: {api.configuration.error}'
        for route in routes:
            if action == 'announce':
                neighbor.rib.outgoing.add_to_rib(neighbor.resolve_self(route))
            else:
                neighbor.rib.outgoing.del_from_rib(route)
    _, negotiated = _negotiated(neighbor)
    updates = neighbor.rib.outgoing.updates(neighbor.group_updates, negotiated=negotiated)
    messages = [
        message for update in updates if isinstance(update, UpdateCollection) for message in update.messages(negotiated)
    ]
    assert len(messages) == 1, f'{len(messages)} UPDATEs for {command!r}'
    return messages[0][19:].hex()


@pytest.mark.parametrize(
    'command',
    [
        # the attributes every UPDATE carries when the route gives none are left out
        'announce route 10.0.0.0/24 next-hop 192.0.2.1',
        # and said when they are not those
        'announce route 10.0.0.0/24 next-hop 192.0.2.1 origin egp local-preference 200',
        'announce route 10.0.0.0/24 rd 65000:1 label [ 100 ] next-hop 192.0.2.1',
        'announce route 10.0.0.0/24 next-hop 192.0.2.1 extended-community [ target:65000:1 0x8006000000000000 ]',
        'withdraw route 10.0.0.0/24',
        # routes which differ by their prefix only are one command
        'announce attributes next-hop 192.0.2.1 med 5 nlri 10.0.0.0/24 10.0.1.0/24',
        'announce ipv4 rtc origin-as 65000 route-target 65000:1 next-hop 192.0.2.1',
        'withdraw ipv4 rtc origin-as 65000 route-target 65000:1',
        'announce ipv4 flow destination-ipv4 10.0.0.0/24 rate-limit 0',
        # the actions in the order of their communities on the wire
        'announce ipv4 flow destination-ipv4 10.0.0.0/24 action sample-terminal redirect 65000:1 mark 10',
        'withdraw ipv4 flow destination-ipv4 10.0.0.0/24',
        # the flow line of an address family has no next-hop: the route block of `flow` does
        'announce flow route { match { destination-ipv4 10.0.0.0/24; } then { redirect-to-nexthop; } next-hop 192.0.2.9; }',
        'withdraw vpls rd 192.168.201.1:123 endpoint 5 base 10702 offset 1 size 8',
        'withdraw ipv4 sr-policy distinguisher 0 color 100 endpoint 10.0.0.1',
    ],
)
def test_the_command_of_an_update_sends_it_again(neighbor: Neighbor, command: str) -> None:
    assert decode_to_api_command(_sent(neighbor, command), neighbor) == [command]


def test_an_end_of_rib_marker(neighbor: Neighbor) -> None:
    assert decode_to_api_command('00000000', neighbor) == ['announce eor ipv4 unicast']
    assert decode_to_api_command('00000006800f03000201', neighbor) == ['announce eor ipv6 unicast']


def test_routes_an_rd_tells_apart_are_a_group(neighbor: Neighbor) -> None:
    """`nlri` gives prefixes only. The reactor packs ipv4 unicast and mcast-vpn routes in one
    UPDATE and no other family (rib/outgoing._select_updates), so this one is built by hand.
    """
    api = API(cast(Reactor, None))
    first = 'route 10.0.0.0/24 rd 65000:1 label [ 100 ] next-hop 192.0.2.1'
    second = 'route 10.0.1.0/24 rd 65000:1 label [ 100 ] next-hop 192.0.2.1'
    routes = [*_parse_routes(api, first, action='announce'), *_parse_routes(api, second, action='announce')]
    _, negotiated = _negotiated(neighbor)
    announced = [RoutedNLRI(route.nlri, route.nexthop) for route in routes]
    (message,) = UpdateCollection(announced, [], routes[0].attributes).messages(negotiated)
    assert decode_to_api_command(message[19:].hex(), neighbor) == [f'group announce {first} ; announce {second}']
