"""A flow route of the configuration is the neighbor's once.

The flow section handed the neighbor the list of routes the neighbor also took for itself,
so each flow route was in `neighbor.routes` twice: `exabgp configuration export` listed it
twice and `configuration validate` inserted it twice. The RIB keyed it once, so a peer was
sent it once. Found by qa/bin/test_old_configs.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.configuration import Configuration

NEIGHBOR = 'neighbor 127.0.0.1 {{ router-id 10.0.0.2; local-address 127.0.0.1; local-as 1; peer-as 1; {body} }}'
FLOW = 'route {name} {{ match {{ source 10.0.0.{n}/32; }} then {{ discard; }} }}'


def routes(*configuration: str) -> list[list[str]]:
    loaded = Configuration([' '.join(configuration)], text=True)
    assert loaded.reload(), loaded.error
    return [[str(route.nlri) for route in neighbor.routes] for neighbor in loaded.neighbors.values()]


@pytest.mark.parametrize('count', [1, 2, 3])
def test_each_flow_route_is_the_neighbors_once(count: int) -> None:
    flows = ' '.join(FLOW.format(name=f'r{n}', n=n) for n in range(count))
    (found,) = routes(NEIGHBOR.format(body=f'flow {{ {flows} }}'))
    assert len(found) == count
    assert len(set(found)) == count


def test_flow_and_static_routes_together() -> None:
    body = f'static {{ route 10.1.0.0/24 next-hop 1.2.3.4; }} flow {{ {FLOW.format(name="r", n=1)} }}'
    (found,) = routes(NEIGHBOR.format(body=body))
    assert len(found) == 2


def test_two_neighbors_keep_their_own_flow_routes() -> None:
    first = NEIGHBOR.format(body=f'flow {{ {FLOW.format(name="a", n=1)} }}')
    second = NEIGHBOR.replace('127.0.0.1 {{', '127.0.0.2 {{').format(body=f'flow {{ {FLOW.format(name="b", n=2)} }}')
    assert routes(first, second) == [['flow source-ipv4 10.0.0.1/32'], ['flow source-ipv4 10.0.0.2/32']]
