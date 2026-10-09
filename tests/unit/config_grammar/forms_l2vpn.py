"""The forms of a VPLS route, written against the legacy parser.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

VPLS = 'endpoint 5 base 10702 offset 1 size 8 rd 1:1 next-hop 10.0.0.1'
VPLS_BLOCK = 'endpoint 5; base 10702; offset 1; size 8; rd 1:1; next-hop 10.0.0.1;'

# (the value, as given after a complete vpls route, whether the legacy parser accepts it)
VPLS_VALUE_FORMS: list[tuple[str, bool]] = [
    ('endpoint 0', True),
    ('endpoint 65535', True),
    ('endpoint 65536', False),
    ('endpoint x', False),
    ('base 1', True),
    ('base 1048575', False),  # base + size past the twenty bit label space
    ('offset 65536', False),
    ('size 0', True),
    ('size x', False),
    ('rd 10.0.0.1:1', True),
    ('rd x', False),
    ('next-hop 10.0.0.2', True),
    ('next-hop self', False),  # an IPv4 local address for an l2vpn route
    ('next-hop nowhere', False),
    ('origin egp', True),
    ('origin x', False),
    ('med 5', True),
    ('as-path [ 1 2 ]', True),
    ('local-preference 5', True),
    ('atomic-aggregate', True),
    ('aggregator (1:10.0.0.1)', True),
    ('originator-id 10.0.0.1', True),
    ('cluster-list [ 10.0.0.1 ]', True),
    ('community [ 1:1 no-export ]', True),
    ('extended-community target:1:1', True),
    ('attribute [ 0x20 0xc0 0x00000001 ]', True),
    ('name site', True),
    ('split /24', True),
    ('watchdog dog', True),
    ('withdraw', True),
    ('attribute 0x20', False),
    *[
        (f'{keyword} x', False)
        for keyword in (
            'med',
            'as-path',
            'local-preference',
            'aggregator',
            'originator-id',
            'cluster-list',
            'community',
            'extended-community',
            'split',
        )
    ],
    ('watchdog withdraw', False),
    ('unknown 1', False),
]

# statements of the l2vpn section, after a complete vpls route: each belongs in a vpls route
# and is refused (an attribute went to the last route read, a static one included)
L2VPN_LEVEL_FORMS: list[tuple[str, bool]] = [
    ('origin egp', False),
    ('community 1:1', False),
    ('name x', False),
    ('split /24', False),
    ('med x', False),
    ('rd 2:2', False),
    ('endpoint 7', False),
    ('base 1', False),
    ('offset 1', False),
    ('size 1', False),
    ('next-hop 10.0.0.2', False),
    *[
        (f'{keyword} {value}', False)
        for keyword, value in (
            ('as-path', '[ 1 ]'),
            ('local-preference', '5'),
            ('aggregator', '(1:10.0.0.1)'),
            ('originator-id', '10.0.0.1'),
            ('cluster-list', '10.0.0.1'),
            ('extended-community', 'target:1:1'),
            ('attribute', '[ 0x20 0xc0 0x00000001 ]'),
            ('watchdog', 'dog'),
            ('atomic-aggregate', ''),
            ('withdraw', ''),
        )
    ],
    *[
        (f'{keyword} x', False)
        for keyword in (
            'origin',
            'as-path',
            'local-preference',
            'aggregator',
            'originator-id',
            'cluster-list',
            'community',
            'extended-community',
            'attribute',
            'split',
        )
    ],
    ('watchdog withdraw', False),
]

L2VPN_DOCUMENT_BODIES: list[tuple[str, bool]] = [
    (f'l2vpn {{ vpls {VPLS}; }}', True),
    (f'l2vpn {{ vpls site {{ {VPLS_BLOCK} }} }}', True),
    (f'l2vpn {{ vpls {{ {VPLS_BLOCK} origin igp; }} }}', True),
    ('l2vpn { vpls endpoint 5 base 10702; }', False),
    ('l2vpn { vpls x { endpoint 5; } }', False),
    ('l2vpn { origin igp; }', False),
    ('static { route 10.0.0.0/24 next-hop 1.1.1.1; } l2vpn { origin egp; }', False),  # it changed the static route
    (
        f'static {{ route 10.0.0.0/24 next-hop 1.1.1.1; }} l2vpn {{ vpls {VPLS}; }} static {{ route 10.0.1.0/24 next-hop 1.1.1.1; }}',
        True,
    ),
    (f'l2vpn {{ vpls {VPLS}; }} l2vpn {{ vpls {VPLS}; }}', True),
    (f'l2vpn {{ vpls x {{ vpls {VPLS}; }} }}', False),
    (f'l2vpn {{ vpls {VPLS} route-distinguisher 1:1; }}', False),
    (f'announce {{ l2vpn {{ vpls {VPLS}; }} }}', True),
    (f'announce {{ l2vpn {{ vpls {VPLS} name x origin igp; }} }}', True),
    ('announce { l2vpn { vpls endpoint 5; } }', False),
    ('announce { l2vpn { unicast 10.0.0.0/24; } }', False),
]
