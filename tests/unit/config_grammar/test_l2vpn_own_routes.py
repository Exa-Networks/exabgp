"""The l2vpn section holds VPLS routes, and what is given in it belongs to one of them.

An attribute given in the section went to the last route read, whichever it was, a static
route included: `static { route ...; } l2vpn { origin egp; }` changed the static route.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.read import read_text

NEIGHBOR = (
    'neighbor 127.0.0.2 {{ router-id 10.0.0.1; local-address 127.0.0.1; local-as 1; peer-as 2; '
    'family {{ ipv4 unicast; l2vpn vpls; }} {body} }}'
)
VPLS = 'vpls v { endpoint 5; base 10702; offset 1; size 8; rd 1:1; next-hop 192.0.2.1; }'


@pytest.mark.parametrize('statement', ['origin egp;', 'med 5;', 'endpoint 6;'])
def test_a_value_given_in_the_l2vpn_section_is_refused(statement: str) -> None:
    body = 'static { route 10.0.0.0/24 next-hop 192.0.2.1; } l2vpn { ' + VPLS + ' ' + statement + ' }'
    with pytest.raises(ConfigError, match='is given in a vpls route'):
        read_text(NEIGHBOR.format(body=body))


def test_the_routes_of_the_neighbor_are_all_kept() -> None:
    body = 'static { route 10.0.0.0/24 next-hop 192.0.2.1; } l2vpn { ' + VPLS + ' }'
    routes = read_text(NEIGHBOR.format(body=body)).neighbors[0].routes
    assert sorted(route.nlri.family().afi_safi()[1].name() for route in routes) == ['unicast', 'vpls']
