"""An attribute given twice for one route: a list one adds to the first, any other is refused.

The second was dropped without a word: `med 10 med 20` sent 10, `community 1:1 community 2:2`
sent 1:1 alone. Extended communities were the exception, they merged.
"""

from __future__ import annotations

from typing import Any

import pytest

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.read import read_command, read_text
from exabgp.rib.route import Route

NEIGHBOR = (
    'neighbor 192.0.2.1 {{ router-id 192.0.2.2; local-address 192.0.2.2; local-as 65001; peer-as 65002; '
    'static {{ {static} }} }}'
)


def _static(static: str) -> Route:
    settings = read_text(NEIGHBOR.format(static=static))
    routes = settings.neighbors[0].routes
    assert len(routes) == 1
    return routes[0]


def _announce(line: str) -> Route:
    routes, _ = read_command('ipv4', f'unicast 10.0.0.0/24 next-hop 192.0.2.3 {line}', True)
    assert len(routes) == 1
    route: Route = routes[0]
    return route


def _texts(route: Route, code: int) -> list[str]:
    attribute: Any = route.attributes[code]
    return [str(each) for each in attribute.communities]


MERGED = {
    'community': ('community 1:1 community [ 2:2 3:3 ]', Attribute.CODE.COMMUNITY, ['1:1', '2:2', '3:3']),
    'large-community': (
        'large-community 1:1:1 large-community 2:2:2',
        Attribute.CODE.LARGE_COMMUNITY,
        ['1:1:1', '2:2:2'],
    ),
    'extended-community': (
        'extended-community target:1:1 extended-community target:2:2',
        Attribute.CODE.EXTENDED_COMMUNITY,
        ['target:1:1', 'target:2:2'],
    ),
}


@pytest.mark.parametrize('line,code,wanted', MERGED.values(), ids=MERGED.keys())
def test_a_list_attribute_given_twice_on_a_route_line_is_merged(line: str, code: int, wanted: list[str]) -> None:
    route = _static(f'route 10.0.0.0/24 next-hop 192.0.2.3 {line};')
    assert sorted(_texts(route, code)) == sorted(wanted)


def test_a_list_attribute_given_twice_in_a_route_block_is_merged() -> None:
    route = _static('route 10.0.0.0/24 { next-hop 192.0.2.3; community 1:1; community 2:2; }')
    assert _texts(route, Attribute.CODE.COMMUNITY) == ['1:1', '2:2']


def test_a_list_attribute_given_twice_in_an_api_command_is_merged() -> None:
    route = _announce('community 1:1 community 2:2')
    assert _texts(route, Attribute.CODE.COMMUNITY) == ['1:1', '2:2']


REFUSED = [
    'med 10 med 20',
    'local-preference 10 local-preference 20',
    'as-path [ 1 ] as-path [ 2 ]',
    'origin igp origin egp',
]


@pytest.mark.parametrize('line', REFUSED)
def test_a_single_attribute_given_twice_on_a_route_line_is_refused(line: str) -> None:
    with pytest.raises(ConfigError, match='given twice'):
        _static(f'route 10.0.0.0/24 next-hop 192.0.2.3 {line};')


def test_a_single_attribute_given_twice_in_a_route_block_is_refused() -> None:
    with pytest.raises(ConfigError, match='med is given twice'):
        _static('route 10.0.0.0/24 { next-hop 192.0.2.3; med 10; med 20; }')


def test_a_single_attribute_given_twice_in_an_api_command_is_refused() -> None:
    with pytest.raises(ValueError, match='med is given twice'):
        _announce('med 10 med 20')


def test_a_raw_attribute_of_a_list_code_is_not_merged_with_a_parsed_one() -> None:
    with pytest.raises(ConfigError, match='given twice'):
        _static('route 10.0.0.0/24 next-hop 192.0.2.3 community 1:1 attribute [ 0x08 0xc0 0x00020002 ];')
