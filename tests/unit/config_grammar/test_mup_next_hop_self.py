"""`next-hop self` on a MUP route is of the route's address family.

It took the family of the last prefix read, which a MUP route does not set: on an IPv6 route
`self` had no family, and could not be made the local address.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.read import read_command
from exabgp.protocol.family import AFI


@pytest.mark.parametrize(
    ('afi', 'route', 'family'),
    [
        ('ipv6', 'mup mup-isd 2001::/64 rd 100:100 next-hop self', AFI.ipv6),
        ('ipv4', 'mup mup-isd 10.0.0.0/24 rd 100:100 next-hop self', AFI.ipv4),
    ],
)
def test_self_is_of_the_family_of_the_route(afi: str, route: str, family: AFI) -> None:
    (read,), _ = read_command(afi, route, True)
    assert read.nexthop.SELF
    assert read.nexthop.afi == family
