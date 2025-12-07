"""community/__init__.py

BGP Community Attributes Package.

Community Types:
+------------------+------+--------+--------------------------------+
| Type             | Code | Size   | RFC                            |
+------------------+------+--------+--------------------------------+
| Standard         | 8    | 4 bytes| RFC 1997                       |
| Extended         | 16   | 8 bytes| RFC 4360                       |
| Large            | 32   | 12 bytes| RFC 8092                      |
+------------------+------+--------+--------------------------------+

Standard Community Format (RFC 1997):
+-----------------------------------+
|    High (2 octets)                |  Typically ASN
+-----------------------------------+
|    Low (2 octets)                 |  Value
+-----------------------------------+

Extended Community Format (RFC 4360):
+-----------------------------------+
|    Type (1 octet)                 |
+-----------------------------------+
|    Sub-Type (1 octet)             |
+-----------------------------------+
|    Value (6 octets)               |
+-----------------------------------+

Large Community Format (RFC 8092):
+-----------------------------------+
|    Global Administrator (4 oct)   |
+-----------------------------------+
|    Local Data Part 1 (4 octets)   |
+-----------------------------------+
|    Local Data Part 2 (4 octets)   |
+-----------------------------------+

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#community-types

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.attribute.community.initial.community import Community
from exabgp.bgp.message.update.attribute.community.initial.communities import Communities

from exabgp.bgp.message.update.attribute.community.large.community import LargeCommunity
from exabgp.bgp.message.update.attribute.community.large.communities import LargeCommunities

from exabgp.bgp.message.update.attribute.community.extended.community import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunities

__all__ = [
    'Community',
    'Communities',
    'LargeCommunity',
    'LargeCommunities',
    'ExtendedCommunity',
    'ExtendedCommunities',
]
