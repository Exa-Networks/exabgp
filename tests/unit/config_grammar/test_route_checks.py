"""A configured route is refused when the neighbor could never send it as written.

Three were accepted and failed later, or went out wrong: a link-local next-hop without the
link-local next-hop capability, an IPv4 unicast route for a neighbor whose family block does
not negotiate IPv4 unicast, and an IPv4 route with an IPv6 next-hop without the Extended Next
Hop Encoding (RFC 8950) asked for that family.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.read import read_text

NEIGHBOR = (
    'neighbor 192.0.2.1 {{ router-id 192.0.2.2; local-address 192.0.2.2; local-as 65001; peer-as 65002; {extra} }}'
)


def _read(extra: str) -> int:
    settings = read_text(NEIGHBOR.format(extra=extra))
    return sum(len(neighbor.routes) for neighbor in settings.neighbors)


def test_a_link_local_next_hop_with_the_capability_is_read() -> None:
    extra = (
        'family { ipv6 unicast; } capability { link-local-nexthop enable; } '
        'static { route 2001:db8::/32 next-hop fe80::1; }'
    )
    assert _read(extra) == 1


def test_a_link_local_next_hop_without_the_capability_is_refused() -> None:
    with pytest.raises(ConfigError, match='link-local'):
        _read('family { ipv6 unicast; } static { route 2001:db8::/32 next-hop fe80::1; }')


def test_an_ipv4_route_of_a_negotiated_family_is_read() -> None:
    assert _read('family { ipv4 unicast; ipv6 unicast; } static { route 10.0.0.0/24 next-hop 192.0.2.3; }') == 1


def test_an_ipv4_route_of_a_family_not_negotiated_is_refused() -> None:
    with pytest.raises(ConfigError, match='not announcing the family'):
        _read('family { ipv6 unicast; } static { route 10.0.0.0/24 next-hop 192.0.2.3; }')


def test_an_ipv4_route_with_an_ipv6_next_hop_and_extended_next_hop_is_read() -> None:
    extra = (
        'family { ipv4 unicast; ipv6 unicast; } nexthop { ipv4 unicast ipv6; } '
        'static { route 10.0.0.0/24 next-hop 2001:db8::1; }'
    )
    assert _read(extra) == 1


def test_an_ipv4_route_with_an_ipv6_next_hop_without_extended_next_hop_is_refused() -> None:
    with pytest.raises(ConfigError, match='RFC 8950'):
        _read('family { ipv4 unicast; } static { route 10.0.0.0/24 next-hop 2001:db8::1; }')


def test_an_ipv4_vpn_route_with_an_ipv6_next_hop_without_extended_next_hop_is_refused() -> None:
    with pytest.raises(ConfigError, match='RFC 8950'):
        _read('family { ipv4 mpls-vpn; } static { route 10.0.0.0/24 rd 1:1 label 5 next-hop 2001:db8::1; }')
