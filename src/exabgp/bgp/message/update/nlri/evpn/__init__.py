"""evpn/__init__.py

BGP EVPN (Ethernet VPN) NLRI Implementation.

Reference: RFC 7432 - BGP MPLS-Based Ethernet VPN
           https://datatracker.ietf.org/doc/html/rfc7432

EVPN NLRI Format (Section 7):
+-----------------------------------+
|    Route Type (1 octet)           |
+-----------------------------------+
|    Length (1 octet)               |
+-----------------------------------+
|    Route Type specific (variable) |
+-----------------------------------+

Route Types (Section 7.1-7.5):
- Type 1: Ethernet Auto-Discovery - EthernetAD
- Type 2: MAC/IP Advertisement - MAC
- Type 3: Inclusive Multicast Ethernet Tag - Multicast
- Type 4: Ethernet Segment - EthernetSegment
- Type 5: IP Prefix Route - Prefix (RFC 9136)

AFI/SAFI: L2VPN (25) / EVPN (70)

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#evpn-rfc-7432

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2014-2017 Orange. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Every EVPN should be imported from this file
# as it makes sure that all the registering decorator are run

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN

from exabgp.bgp.message.update.nlri.evpn.ethernetad import EthernetAD
from exabgp.bgp.message.update.nlri.evpn.mac import MAC
from exabgp.bgp.message.update.nlri.evpn.multicast import Multicast
from exabgp.bgp.message.update.nlri.evpn.segment import EthernetSegment
from exabgp.bgp.message.update.nlri.evpn.prefix import Prefix

__all__ = [
    'EVPN',
    'EthernetAD',
    'MAC',
    'Multicast',
    'EthernetSegment',
    'Prefix',
]
