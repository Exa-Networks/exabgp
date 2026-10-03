"""A route given `next-hop` twice takes the first one, address and attribute alike.

The address was the last and the NEXT_HOP attribute the first, so `next-hop self next-hop
1.2.3.4` made a route whose attribute still said self and could not be packed. 5.0 sent the
first for IPv4 unicast (and the last for the MP families). Found by qa/bin/test_old_commands.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.reactor.api import API


@pytest.mark.parametrize(
    'command,parse',
    [
        ('announce route 10.0.0.0/24 next-hop 1.2.3.4 next-hop self', 'api_route'),
        ('announce ipv4 unicast 10.0.0.0/24 next-hop 1.2.3.4 next-hop self', 'api_announce_v4'),
        ('announce ipv4 multicast 192.0.2.0/24 next-hop 1.2.3.4 next-hop self', 'api_announce_v4'),
        ('announce ipv4 unicast 10.0.0.0/24 next-hop 1.2.3.4 next-hop 5.6.7.8', 'api_announce_v4'),
    ],
)
def test_the_first_next_hop_is_the_route_s(command: str, parse: str) -> None:
    (route,) = getattr(API(MagicMock()), parse)(command)
    assert str(route.nexthop) == '1.2.3.4'
    assert str(route.attributes[Attribute.CODE.NEXT_HOP]) == '1.2.3.4'
