"""A flow route takes its address family from what it matches, not from the line before it.

A component was checked against the family of the last prefix read anywhere, a static route's
included, so an IPv6 flow route written after an IPv4 static route refused its flow-label.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.read import read_command, read_text

NEIGHBOR = (
    'neighbor 127.0.0.2 {{ router-id 10.0.0.1; local-address 127.0.0.1; local-as 1; peer-as 2; '
    'family {{ ipv4 unicast; ipv4 flow; ipv6 flow; }} {body} }}'
)
STATIC = 'static { route 10.1.0.0/24 next-hop 192.0.2.1; } '


@pytest.mark.parametrize(
    'flow',
    [
        'flow { route r { match { flow-label =5; destination-ipv6 2001:db8::/32/0; } then { discard; } } }',
        'flow { route flow-label =5 destination-ipv6 2001:db8::/32/0 discard; }',
    ],
)
def test_an_ipv6_flow_route_after_an_ipv4_static_route(flow: str) -> None:
    routes = read_text(NEIGHBOR.format(body=STATIC + flow)).neighbors[0].routes
    assert [str(route.nlri.afi) for route in routes] == ['ipv4', 'ipv6']


def test_an_announce_line_takes_the_family_of_its_block() -> None:
    (route,), _ = read_command('ipv6', 'flow flow-label =5 discard', True)
    assert str(route.nlri.afi) == 'ipv6'
