"""The forms of the MUP and MCAST-VPN routes, written against the legacy parser.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

# (address family, family, the route, whether the legacy parser accepts it)
SELECT_FORMS: list[tuple[str, str, str, bool]] = [
    ('ipv4', 'mup', 'mup-isd 10.0.1.0/24 rd 100:100 next-hop 10.0.0.1', True),
    ('ipv4', 'mup', 'mup-isd 10.0.1.0/24 rd 100:100 next-hop 10.0.0.1 extended-community [ target:10:10 ]', True),
    (
        'ipv4',
        'mup',
        'mup-isd 10.0.1.0/24 rd 100:100 next-hop 10.0.0.1 bgp-prefix-sid-srv6 ( l3-service 2001:db8:1:1:: 0x48 [ 64, 24, 16, 0, 0, 0 ] )',
        True,
    ),
    ('ipv4', 'mup', 'mup-isd 10.0.1.0/24 rd 100:100 next-hop self', True),
    ('ipv4', 'mup', 'mup-isd 10.0.1.0 rd 100:100', False),
    ('ipv4', 'mup', 'mup-isd 10.0.1.0/24 rd x', False),
    ('ipv4', 'mup', 'mup-isd 10.0.1.0/24 next-hop 10.0.0.1', False),
    ('ipv4', 'mup', 'mup-dsd 10.0.0.1 rd 100:100 next-hop 10.0.0.1', True),
    ('ipv4', 'mup', 'mup-dsd 2001:db8::1 rd 100:100', False),
    ('ipv4', 'mup', 'mup-t1st 10.0.1.0/24 rd 100:100 teid 12345 qfi 9 endpoint 10.0.0.1 next-hop 10.0.0.1', True),
    ('ipv4', 'mup', 'mup-t1st 10.0.1.0/24 rd 100:100 teid 12345 qfi 9 endpoint 10.0.0.1 source 10.0.0.2', True),
    ('ipv4', 'mup', 'mup-t1st 10.0.1.0/24 rd 100:100 teid 12345 qfi 64 endpoint 10.0.0.1', False),
    ('ipv4', 'mup', 'mup-t1st 10.0.1.0/24 rd 100:100 teid x qfi 9 endpoint 10.0.0.1', False),
    ('ipv4', 'mup', 'mup-t1st 10.0.1.0/24 rd 100:100 qfi 9', False),
    # draft-mpmz-bess-mup-safi-05 3.1.3.1 and 3.1.4.1 make a TEID of 0 malformed: refused since
    ('ipv4', 'mup', 'mup-t1st 10.0.1.0/24 rd 100:100 teid 0 qfi 9 endpoint 10.0.0.1', False),
    ('ipv4', 'mup', 'mup-t2st 10.0.0.1 rd 100:100 teid 0/8', False),
    ('ipv4', 'mup', 'mup-t2st 10.0.0.1 rd 100:100 teid 0/0 next-hop 10.0.0.1', True),
    ('ipv4', 'mup', 'mup-t2st 10.0.0.1 rd 100:100 teid 12345/32 next-hop 10.0.0.1', True),
    ('ipv4', 'mup', 'mup-t2st 10.0.0.1 rd 100:100 teid 12345/8', False),
    ('ipv4', 'mup', 'mup-t2st 10.0.0.1 rd 100:100 teid 12345', False),
    ('ipv4', 'mup', 'mup-t2st 10.0.0.1 rd 100:100 teid 1/33', False),
    ('ipv4', 'mup', 'mup-nothing 10.0.0.1', False),
    ('ipv4', 'mup', 'mup-dsd 10.0.0.1 rd 100:100 origin igp', False),
    ('ipv6', 'mup', 'mup-isd 2001:db8::/64 rd 100:100 next-hop 2001:db8::1', True),
    ('ipv6', 'mup', 'mup-isd 2001:db8::/64 rd 100:100 next-hop 10.0.0.1', True),
    ('ipv6', 'mup', 'mup-dsd 2001:db8::1 rd 100:100 next-hop 2001:db8::1', True),
    ('ipv6', 'mup', 'mup-t2st 2001:db8::1 rd 100:100 teid 1/8 next-hop 2001:db8::1', True),
    ('ipv4', 'mcast-vpn', 'source-ad source 10.0.0.1 group 239.0.0.1 rd 1:1 next-hop 10.0.0.1', True),
    ('ipv4', 'mcast-vpn', 'source-join source 10.0.0.1 group 239.0.0.1 rd 1:1 source-as 65000 next-hop 10.0.0.1', True),
    ('ipv4', 'mcast-vpn', 'shared-join rp 10.0.0.1 group 239.0.0.1 rd 1:1 source-as 65000 next-hop 10.0.0.1', True),
    ('ipv4', 'mcast-vpn', 'shared-join rp 10.0.0.1 group 239.0.0.1 rd 1:1 source-as 65000 origin igp med 5', True),
    ('ipv4', 'mcast-vpn', 'shared-join rp 10.0.0.1 group 239.0.0.1 rd 1:1 source-as x', False),
    ('ipv4', 'mcast-vpn', 'shared-join rp 10.0.0.1 group 239.0.0.1 rd 1:1 source-as 4294967296', False),
    ('ipv4', 'mcast-vpn', 'shared-join source 10.0.0.1 group 239.0.0.1 rd 1:1 source-as 1', False),
    ('ipv4', 'mcast-vpn', 'source-ad source 10.0.0.1 group 239.0.0.1', False),
    ('ipv4', 'mcast-vpn', 'source-ad source 2001:db8::1 group 239.0.0.1 rd 1:1', False),
    ('ipv4', 'mcast-vpn', 'source-ad source 10.0.0.1 group 239.0.0.1 rd 1:1 name x', True),
    ('ipv4', 'mcast-vpn', 'nothing source 10.0.0.1', False),
    ('ipv6', 'mcast-vpn', 'source-ad source fd00::1 group ff0e::1 rd 1:1 next-hop 10.0.0.1', True),
    ('ipv6', 'mcast-vpn', 'source-join source fd00::1 group ff0e::1 rd 1:1 source-as 65000', True),
    ('ipv6', 'mcast-vpn', 'shared-join rp fd00::1 group ff0e::1 rd 1:1 source-as 65000', True),
    ('ipv6', 'mcast-vpn', 'nothing', False),
    ('ipv6', 'mup', 'nothing', False),
]
