"""A route line is VPN or labelled because of its `rd` or `label`, not because of a word.

The line was searched for the words `rd`, `route-distinguisher` and `label` anywhere, a value
included: `name rd` made the route a VPN route, which carried no route distinguisher and was
made unicast again, and `name label` a labelled one.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.update.nlri import INET, IPVPN, Label
from exabgp.configuration.grammar.read import read_command
from exabgp.protocol.family import SAFI


@pytest.mark.parametrize('name', ['rd', 'route-distinguisher', 'label'])
def test_a_value_spelled_as_a_keyword_does_not_change_the_route(name: str) -> None:
    (route,), _ = read_command('static', f'route 10.0.0.0/24 next-hop 192.0.2.1 name {name}', True)
    assert type(route.nlri) is INET
    assert route.nlri.safi == SAFI.unicast


def test_the_keywords_still_make_the_route() -> None:
    (vpn,), _ = read_command('static', 'route 10.0.0.0/24 next-hop 192.0.2.1 rd 65000:1 label [ 100 ]', True)
    assert isinstance(vpn.nlri, IPVPN)
    (labelled,), _ = read_command('static', 'route 10.0.0.0/24 next-hop 192.0.2.1 label [ 100 ]', True)
    assert isinstance(labelled.nlri, Label) and not isinstance(labelled.nlri, IPVPN)
