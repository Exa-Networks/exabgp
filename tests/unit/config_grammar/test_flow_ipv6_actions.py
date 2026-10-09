"""Two flow actions to IPv6 addresses are both kept, as two IPv4 actions are.

They are communities of one attribute, the IPv6 address specific extended communities: a
second `copy` was dropped without a word, and a `copy` with a `redirect-to-nexthop-ietf` was
refused as `attribute 0x19 is given twice`.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.configuration.grammar.read import read_text

NEIGHBOR = (
    'neighbor 127.0.0.2 {{ router-id 10.0.0.1; local-address 127.0.0.1; local-as 1; peer-as 2; family {{ ipv6 flow; }} '
    'flow {{ route r {{ match {{ destination-ipv6 2001:db8::/32/0; }} then {{ {then} }} }} }} }}'
)


@pytest.mark.parametrize(
    ('then', 'texts'),
    [
        (
            'copy 2001:db8::1; copy 2001:db8::2;',
            ['copy-to-nexthop-ietf 2001:db8::1', 'copy-to-nexthop-ietf 2001:db8::2'],
        ),
        (
            'copy 2001:db8::1; redirect-to-nexthop-ietf 2001:db8::2;',
            ['copy-to-nexthop-ietf 2001:db8::1', 'redirect-to-nexthop-ietf 2001:db8::2'],
        ),
    ],
)
def test_both_ipv6_actions_are_kept(then: str, texts: list[str]) -> None:
    (route,) = read_text(NEIGHBOR.format(then=then)).neighbors[0].routes
    communities = route.attributes[Attribute.CODE.IPV6_EXTENDED_COMMUNITY].communities
    assert sorted(str(each) for each in communities) == texts
