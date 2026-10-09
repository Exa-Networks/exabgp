"""The forms of a FlowSpec route, written against the legacy parser.

Each match is tried in the match block of a route block, in a one-line route and in an
announce family; each action and route value likewise, in its own block.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

# (statement, whether the legacy parser accepts it) of each block of a flow route
MATCH_FORMS: list[tuple[str, bool]] = [
    ('source 10.0.0.0/24', True),
    ('source-ipv4 10.0.0.0/24', True),
    ('destination 10.0.0.0/24', True),
    ('destination-ipv4 10.0.0.0/32', True),
    ('destination 10.0.0.0/33', False),
    ('destination 10.0.0.0', False),
    ('destination nothing', False),
    ('source 2001:db8::/32', True),
    ('source-ipv6 2001:db8::/32/8', True),
    ('destination 2001:db8::/32/40', False),
    ('destination-ipv6 ::/0/0', True),
    ('destination ::/0/1', False),
    ('protocol tcp', True),
    ('protocol [ udp tcp ]', True),
    ('protocol =6', True),
    ('protocol !=6', True),
    ('protocol tcpp', False),
    ('protocol [ tcp', False),
    ('protocol', False),
    ('port 25', True),
    ('port [ =80 =3128 >8080&<8088 ]', True),
    ('port >=1024', True),
    ('port <=1024', True),
    ('port !=80', True),
    ('port !80', False),
    ('port >', False),
    ('port 80&', False),  # a condition ending on & was refused in brackets only
    ('port [ 80& ]', False),
    ('port x', False),
    ('destination-port =80', True),
    ('destination-port =+80', False),  # ASCII digits only
    ('destination-port =8_0', False),
    ('destination 10.0.0.0/2_4', False),
    ('source-port >1024', True),
    ('icmp-type 8', True),
    ('icmp-type echo-request', True),
    ('icmp-code 0', True),
    ('tcp-flags syn', True),
    ('tcp-flags [ syn ack ]', True),
    ('tcp-flags =syn', True),
    ('tcp-flags !syn', True),
    ('tcp-flags !=syn', True),
    ('tcp-flags syn&!ack', True),
    ('tcp-flags nothing', False),
    ('packet-length [ >200&<300 >400&<500 ]', True),
    ('dscp 10', True),
    ('fragment is-fragment', True),
    ('fragment [ dont-fragment first-fragment last-fragment ]', True),
    ('fragment nothing', False),
    ('next-header tcp', True),  # an IPv6 component, taken while no prefix has set the family
    ('flow-label 10', True),
    ('traffic-class 10', True),
    ('port true', False),
    *[
        (f'{keyword} nothing', False)
        for keyword in (
            'source',
            'source-ipv4',
            'source-ipv6',
            'destination-ipv4',
            'destination-ipv6',
            'next-header',
            'destination-port',
            'source-port',
            'icmp-type',
            'icmp-code',
            'packet-length',
            'dscp',
            'traffic-class',
            'flow-label',
        )
    ],
    ('port false', False),
]

THEN_FORMS: list[tuple[str, bool]] = [
    ('accept', True),
    ('accept extra', False),
    ('discard', True),
    ('rate-limit 0', True),
    ('rate-limit 9600', True),
    ('rate-limit 100', True),
    ('rate-limit 100 packets', True),
    ('rate-limit 100 bytes', True),
    ('rate-limit 2000000000000', True),
    ('rate-limit x', False),
    ('rate-limit +100', False),
    ('rate-limit', False),
    ('redirect 65000:1', True),
    ('redirect 4200000000:1', True),
    ('redirect 4200000000:65536', False),
    ('redirect 65000:4294967296', False),
    ('redirect 10.0.0.1', True),
    ('redirect 2001:db8::1', True),
    ('redirect [2001:db8::1]', True),
    ('redirect [2001:db8::1]:100', True),
    ('redirect [2001:db8::1]:65536', False),
    ('redirect [10.0.0.1]:100', False),
    ('redirect 1.2.3.4:100', False),
    ('redirect nothing', False),
    ('redirect-to-nexthop', True),
    ('redirect-to-nexthop 10.0.0.1', True),
    ('redirect-to-nexthop 2001:db8::1', True),
    ('redirect-to-nexthop nothing', False),
    ('redirect-to-nexthop-ietf 10.0.0.1', True),
    ('redirect-to-nexthop-ietf', False),
    ('redirect-to-nexthop-simpson', True),
    ('redirect-simpson 10.0.0.1', True),
    ('redirect-simpson [2001:db8::1]', True),
    ('redirect-simpson 65000:1', False),
    ('copy 10.0.0.1', True),
    ('copy nothing', False),
    ('copy-simpson 10.0.0.1', True),
    ('copy-simpson nothing', False),
    ('mark 0', True),
    ('mark 63', True),
    ('mark 64', False),
    ('mark x', False),
    ('action sample', True),
    ('action terminal', True),
    ('action sample-terminal', True),
    ('action nothing', False),
    ('community 1:1', True),
    ('community x', False),
    ('large-community 1:2:3', True),
    ('large-community x', False),
    ('extended-community target:1:1', True),
    ('extended-community x', False),
]

SCOPE_FORMS: list[tuple[str, bool]] = [
    ('interface-set transitive:input:1234:1234', True),
    ('interface-set non-transitive:output:1:1', True),
    ('interface-set input-output:1:1', True),
    ('interface-set [ input:1:1 output:2:2 ]', True),
    ('interface-set sideways:input:1:1', False),
    ('interface-set input:1.1:1', False),
    ('interface-set up:1:1', False),
    ('interface-set input:1:16384', False),
    ('interface-set input', False),
]

ROUTE_FORMS: list[tuple[str, bool]] = [
    ('rd 65000:1', True),
    ('route-distinguisher 10.0.0.1:1', True),
    ('rd x', False),
    ('route-distinguisher x', False),
    ('path-information 1', True),
    ('path-information 0.0.0.1', True),
    ('path-information x', False),
    ('next-hop 10.0.0.1', True),
    ('next-hop self', True),
    ('next-hop nowhere', False),
]

FLOW_DOCUMENT_BODIES: list[tuple[str, bool]] = [
    ('flow { route r { match { destination 10.0.0.0/24; } then { discard; } } }', True),
    ('flow { route { match { destination 10.0.0.0/24; } } }', True),
    ('flow { route r { then { discard; } } }', False),
    ('flow { route r { } }', False),
    ('flow { route r { match { destination 10.0.0.0/24; source 2001:db8::/32; } } }', False),
    ('flow { route r { match { destination 2001:db8::/32; next-header tcp; } } }', True),
    ('flow { route r { match { destination 10.0.0.0/24; } rd 1:1; then { redirect 1:1; } } }', True),
    ('flow { route r { match { destination 10.0.0.0/24; } then { redirect-simpson 10.0.0.1; } } }', True),
    ('flow { route r { match { destination 10.0.0.0/24; } then { copy-simpson 10.0.0.1; discard; } } }', True),
    # two actions to an IPv6 address are one attribute: the second was dropped, or refused
    (
        'family { ipv6 flow; } flow { route r { match { destination-ipv6 2001:db8::/32/0; } '
        'then { copy 2001:db8::1; copy 2001:db8::2; } } }',
        True,
    ),
    (
        'family { ipv6 flow; } flow { route r { match { destination-ipv6 2001:db8::/32/0; } '
        'then { copy 2001:db8::1; redirect-to-nexthop-ietf 2001:db8::2; } } }',
        True,
    ),
    (
        'flow { route r { match { destination 10.0.0.0/24; } scope { interface-set input:1:1; } then { extended-community target:1:1; } } }',
        True,
    ),
    ('flow { route destination 10.0.0.0/24 discard; }', True),
    ('flow { route destination 10.0.0.0/24; }', True),
    ('flow { route discard; }', False),  # no match: it would match every packet
    ('flow { route destination 10.0.0.0/24 rd 1:1 redirect 1:1; }', True),
    # the rd, as `rd` and as in a route block: it named no field of a flow route, and was refused
    ('flow { route destination 10.0.0.0/24 route-distinguisher 1:1; }', True),
    ('flow { route destination 10.0.0.0/24 next-hop 10.0.0.1; }', False),
    ('flow { route destination 10.0.0.0/24 copy-simpson 10.0.0.1 redirect 1:1; }', True),
    ('flow { route destination 10.0.0.0/24 nothing 1; }', False),
    (
        'flow { route r { match { destination 10.0.0.0/24; } } } flow { route r2 { match { source 10.0.0.0/24; } } }',
        True,
    ),
    ('static { route 10.1.0.0/24 next-hop 10.0.0.1; } flow { route r { match { destination 10.0.0.0/24; } } }', True),
    ('flow { route r { match { destination 10.0.0.0/24; } } } static { route 10.1.0.0/24 next-hop 10.0.0.1; }', True),
    (
        'static { route 2001:db8::/48 next-hop 2001:db8::1; } flow { route r { match { destination 10.0.0.0/24; protocol tcp; } } }',
        True,  # an IPv4 flow route: it was refused for the family of the static route before it
    ),
    ('flow { route r { match { destination 10.0.0.0/24; } } unknown { } } }', False),
    ('announce { ipv4 { flow destination 10.0.0.0/24 discard; } }', True),
    ('announce { ipv4 { flow-vpn rd 1:1 destination 10.0.0.0/24 redirect 1:1; } }', True),
    ('announce { ipv6 { flow destination 2001:db8::/32 next-header tcp discard; } }', True),
    ('announce { ipv4 { flow destination 2001:db8::/32; } }', False),
    ('announce { ipv4 { flow next-hop 10.0.0.1; } }', False),
    ('announce { ipv4 { flow destination 10.0.0.0/24 attribute [ 0x20 0xc0 0x00000001 ]; } }', True),
    # a route with an rd is flow-vpn: on the flow line it made a flow route carrying an rd
    ('announce { ipv4 { flow destination 10.0.0.0/24 route-distinguisher 1:1; } }', False),
    ('announce { ipv4 { flow destination 10.0.0.0/24 rd 1:1; } }', False),
    ('announce { ipv4 { flow-vpn destination 10.0.0.0/24 route-distinguisher 1:1; } }', True),
    ('announce { ipv4 { flow destination 10.0.0.0/24 path-information 1; } }', True),
]
