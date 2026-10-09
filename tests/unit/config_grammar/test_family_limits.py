"""The prefix limits of family blocks add up, and the neighbor's win over its templates'.

The limits of the last block giving any replaced those of the blocks before it, so
`family { ipv4 unicast prefix-limit 5; } family { ipv6 unicast prefix-limit 7; }` lost the
IPv4 limit. A template's limit, or its add-path limit, came after the neighbor's and won.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.read import read_text
from exabgp.protocol.family import AFI, SAFI

V4 = (AFI.ipv4, SAFI.unicast)
V6 = (AFI.ipv6, SAFI.unicast)
NEIGHBOR = (
    'neighbor 127.0.0.2 {{ {inherit} router-id 10.0.0.1; local-address 127.0.0.1; local-as 1; peer-as 2; {body} }}'
)


def _neighbor(body: str, inherit: str = '', templates: str = ''):
    return read_text(templates + NEIGHBOR.format(inherit=inherit, body=body)).neighbors[0]


def test_the_limits_of_two_blocks_add_up() -> None:
    neighbor = _neighbor('family { ipv4 unicast prefix-limit 5; } family { ipv6 unicast prefix-limit 7; }')
    assert neighbor.prefix_limit == {V4: 5, V6: 7}


def test_two_limits_for_one_family_are_refused() -> None:
    with pytest.raises(ConfigError, match='prefix-limit of ipv4 unicast is given twice, 5 and 7'):
        _neighbor('family { ipv4 unicast prefix-limit 5; } family { ipv4 unicast prefix-limit 7; }')


def test_the_limits_of_the_neighbor_win_over_its_template() -> None:
    templates = (
        'template { neighbor t { family { ipv4 unicast prefix-limit 7; } add-path { ipv4 unicast limit 9; } } } '
    )
    body = 'capability { add-path send; } family { ipv4 unicast prefix-limit 5; } add-path { ipv4 unicast limit 3; }'
    neighbor = _neighbor(body, 'inherit t;', templates)
    assert neighbor.prefix_limit == {V4: 5}
    assert neighbor.capability.paths_limit_per_family == {V4: 3}
