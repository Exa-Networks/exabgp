"""Schema-based IP announcements construct immutable NLRI through settings."""

from unittest.mock import Mock

import pytest

from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.api import API


@pytest.mark.parametrize(
    'command,afi,safi,prefix,nexthop',
    [
        ('ipv4 unicast', AFI.ipv4, SAFI.unicast, '10.0.0.0/24', '192.0.2.1'),
        ('ipv4 multicast', AFI.ipv4, SAFI.multicast, '239.0.0.0/8', '192.0.2.1'),
        ('ipv6 unicast', AFI.ipv6, SAFI.unicast, '2001:db8::/32', '2001:db8::1'),
    ],
)
def test_ip_announcement_preserves_family_prefix_and_nexthop(command, afi, safi, prefix, nexthop):
    api = API(Mock())
    parse = api.api_announce_v4 if afi == AFI.ipv4 else api.api_announce_v6
    routes = parse(f'{command} {prefix} next-hop {nexthop}', 'announce')
    assert [(route.nlri.family().afi_safi(), str(route.nlri.cidr), str(route.nexthop)) for route in routes] == [
        ((afi, safi), prefix, nexthop)
    ]
