"""The forms of the operational messages, written against the legacy parser.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

# (the statement in an operational block, whether the legacy parser accepts it)
OPERATIONAL_FORMS: list[tuple[str, bool]] = [
    ('asm afi ipv4 safi unicast advisory "a b"', True),
    ('adm afi ipv6 safi unicast advisory x', True),
    ('adm afi ipv6 safi unicast', False),
    ('asm AFI ipv4 SAFI unicast ADVISORY x', True),
    ('asm afi ipv4 safi unicast advisory x trailing words', True),
    ('asm afi ipv4 safi unicast', False),
    ('asm afi ipv4 safi nothing advisory x', False),
    ('asm afi nothing safi unicast advisory x', False),
    ('asm safi unicast afi ipv4 advisory x', False),
    ('asm afi ipv4 safi unicast router-id 1.2.3.4', False),
    ('asm afi ipv4 safi unicast advisory x router-id 1.2.3.4', True),
    ('rpcq afi ipv4 safi unicast sequence 5', True),
    ('rpcq afi ipv4 safi unicast sequence 0', True),
    ('rpcq afi ipv4 safi unicast sequence -1', True),
    ('rpcq afi ipv4 safi unicast sequence 4294967295', True),
    ('rpcq afi ipv4 safi unicast sequence 4294967296', False),
    ('rpcq afi ipv4 safi unicast sequence x', False),
    ('rpcq afi ipv4 safi unicast router-id 1.2.3.4 sequence 5', False),
    ('rpcq afi ipv4 safi unicast router-id x sequence 5', False),
    ('apcq afi ipv4 safi mpls-vpn sequence 5', True),
    ('apcq afi ipv4 safi mpls-vpn', False),
    ('lpcq afi ipv6 safi unicast sequence 5', True),
    ('lpcq afi ipv6 safi unicast', False),
    ('rpcp afi ipv4 safi unicast sequence 1 counter 9', True),
    ('rpcp afi ipv4 safi unicast sequence 1 counter 4294967295', True),
    ('rpcp afi ipv4 safi unicast sequence 1 counter 4294967296', False),
    ('rpcp afi ipv4 safi unicast sequence 1 counter -1', False),
    ('apcp afi ipv4 safi unicast sequence 1 counter x', False),
    ('lpcp afi ipv4 safi unicast counter 1 sequence 1', False),
    ('lpcp afi ipv4 safi unicast sequence 1', False),
    ('rpcp afi ipv4 safi unicast sequence 1', False),
    ('apcp afi ipv4 safi unicast sequence 1 counter 1', True),
    ('lpcp afi ipv4 safi unicast sequence 1 counter 1', True),
]

# whole neighbor bodies: several messages, several blocks, a template
OPERATIONAL_DOCUMENT_BODIES: list[tuple[str, bool]] = [
    (
        'operational { rpcq afi ipv4 safi unicast sequence 1; asm afi ipv4 safi unicast advisory a; '
        'apcp afi ipv4 safi unicast sequence 2 counter 3; rpcq afi ipv4 safi unicast sequence 4; '
        'asm afi ipv4 safi unicast advisory b; }',
        True,
    ),
    # a second block replaces the first
    (
        'operational { rpcq afi ipv4 safi unicast sequence 1; } operational { apcq afi ipv4 safi unicast sequence 2; }',
        True,
    ),
    # a message of a family the neighbor does not have is dropped
    ('family { ipv4 unicast; } operational { rpcq afi ipv6 safi unicast sequence 1; }', True),
    ('operational { }', True),
    # an empty block keeps the messages of the one before
    ('operational { rpcq afi ipv4 safi unicast sequence 1; } operational { }', True),
    ('operational { nothing; }', False),
]
