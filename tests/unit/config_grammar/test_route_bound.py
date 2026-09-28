"""A route statement reads at most MAX_ROUTE_VALUES keyword and value pairs, and refuses a line with more."""

from __future__ import annotations

from typing import Callable

import pytest

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.read import read_command, read_text
from exabgp.configuration.grammar.types.route import MAX_ROUTE_VALUES

NEIGHBOR = (
    'neighbor 192.0.2.1 {{ router-id 192.0.2.2; local-address 192.0.2.2; local-as 65001; peer-as 65002; {extra} }}'
)


def _announce(count: int) -> None:
    # `next-hop` is the first value, `med` the others
    read_command('ipv4', 'unicast 10.0.0.0/24 next-hop 192.0.2.3' + ' med 1' * (count - 1), True)


def _static(count: int) -> None:
    route = 'route 10.0.0.0/24 next-hop 192.0.2.3' + ' med 1' * (count - 1)
    read_text(NEIGHBOR.format(extra=f'static {{ {route}; }}'))


STATEMENTS = {'announce': _announce, 'static': _static}


@pytest.mark.parametrize('read', STATEMENTS.values(), ids=STATEMENTS.keys())
def test_a_route_of_the_most_values_is_read(read: Callable[[int], None]) -> None:
    read(MAX_ROUTE_VALUES)


@pytest.mark.parametrize('read', STATEMENTS.values(), ids=STATEMENTS.keys())
def test_a_route_of_one_value_more_is_refused(read: Callable[[int], None]) -> None:
    with pytest.raises(ConfigError, match=f'at most {MAX_ROUTE_VALUES} values'):
        read(MAX_ROUTE_VALUES + 1)
