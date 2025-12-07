"""qualifier/__init__.py

Common NLRI Qualifier/Component Types.

These building blocks are used by multiple NLRI types (EVPN, IPVPN, etc.)
to encode common fields like Route Distinguishers, Labels, and MACs.

Qualifiers and their RFC references:
- ESI (Ethernet Segment Identifier) - RFC 7432 Section 5
- EthernetTag - RFC 7432 Section 7.1
- Labels (MPLS) - RFC 3107, RFC 8277
- MAC (Ethernet Address) - IEEE 802, RFC 7432
- PathInfo (ADD-PATH) - RFC 7911
- RouteDistinguisher - RFC 4364 Section 4.2

Route Distinguisher Types (RFC 4364):
- Type 0: 2-byte ASN : 4-byte value
- Type 1: 4-byte IPv4 : 2-byte value
- Type 2: 4-byte ASN : 2-byte value

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#common-building-blocks

Created by Thomas Mangin on 2015-06-01.
Copyright (c) 2015-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Every Qualifier should be imported from this file

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.nlri.qualifier.esi import ESI
from exabgp.bgp.message.update.nlri.qualifier.etag import EthernetTag
from exabgp.bgp.message.update.nlri.qualifier.labels import Labels
from exabgp.bgp.message.update.nlri.qualifier.mac import MAC
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher

__all__ = [
    'ESI',
    'EthernetTag',
    'Labels',
    'MAC',
    'PathInfo',
    'RouteDistinguisher',
]
