"""`split` makes at most MAX_SPLIT_ROUTES more specifics, and only more specifics of its prefix.

A split was unbounded: `route 2001:db8::/32 split /128` asked for 2**96 routes and the read never
ended. A split shorter than the prefix, or longer than an address, was taken silently.
"""

from __future__ import annotations

import math

import pytest

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.read import read_command, read_text
from exabgp.configuration.grammar.tree.static import MAX_SPLIT_ROUTES

NEIGHBOR = (
    'neighbor 192.0.2.1 {{ router-id 192.0.2.2; local-address 192.0.2.2; local-as 65001; peer-as 65002; '
    'family {{ ipv4 unicast; ipv6 unicast; }} static {{ {route}; }} }}'
)
WIDEST = 32 - int(math.log2(MAX_SPLIT_ROUTES))  # the shortest IPv4 prefix split into /32 within the bound


def _routes(route: str) -> int:
    settings = read_text(NEIGHBOR.format(route=route))
    return sum(len(neighbor.routes) for neighbor in settings.neighbors)


def test_a_split_into_the_most_routes_is_read() -> None:
    assert _routes(f'route 10.0.0.0/{WIDEST} next-hop 192.0.2.3 split /32') == MAX_SPLIT_ROUTES


def test_a_split_into_one_route_more_is_refused() -> None:
    with pytest.raises(ConfigError, match=f'more than {MAX_SPLIT_ROUTES} routes'):
        _routes(f'route 10.0.0.0/{WIDEST - 1} next-hop 192.0.2.3 split /32')


def test_an_ipv6_split_into_host_routes_is_refused_without_making_them() -> None:
    with pytest.raises(ConfigError, match=f'more than {MAX_SPLIT_ROUTES} routes'):
        _routes('route 2001:db8::/32 next-hop 2001:db8::1 split /128')


def test_a_split_shorter_than_the_prefix_is_refused() -> None:
    with pytest.raises(ConfigError, match='shorter than the prefix'):
        _routes('route 10.0.0.0/24 next-hop 192.0.2.3 split /23')


def test_a_split_longer_than_an_address_is_refused() -> None:
    with pytest.raises(ConfigError, match='longer than an address'):
        _routes('route 10.0.0.0/31 next-hop 192.0.2.3 split /33')


def test_a_split_as_long_as_the_prefix_is_the_route_itself() -> None:
    assert _routes('route 10.0.0.0/24 next-hop 192.0.2.3 split /24') == 1


def test_an_api_split_past_the_bound_is_refused() -> None:
    with pytest.raises(ValueError, match=f'more than {MAX_SPLIT_ROUTES} routes'):
        read_command('ipv6', 'unicast 2001:db8::/32 next-hop 2001:db8::1 split /128', True)
