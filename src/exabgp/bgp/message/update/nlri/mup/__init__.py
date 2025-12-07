"""mup/__init__.py

BGP Mobile User Plane (MUP) SAFI Implementation.

Reference: draft-mpmz-bess-mup-safi (BGP Extensions for the Mobile User Plane SAFI)

BGP-MUP NLRI Format (RFC 4760 MP_REACH_NLRI / MP_UNREACH_NLRI):
+-----------------------------------+
|    Architecture Type (1 octet)    |
+-----------------------------------+
|       Route Type (2 octets)       |
+-----------------------------------+
|         Length (1 octet)          |
+-----------------------------------+
|  Route Type specific (variable)   |
+-----------------------------------+

Route Types (Architecture Type 1 = 3GPP-5G):
- Type 1: Interwork Segment Discovery (ISD) - srv6_mup_isd
- Type 2: Direct Segment Discovery (DSD) - srv6_mup_dsd
- Type 3: Type 1 Session Transformed (T1ST) - srv6_mup_t1st
- Type 4: Type 2 Session Transformed (T2ST) - srv6_mup_t2st

Important: MPLS labels for MUP are NOT part of the NLRI.
Per draft-mpmz-bess-mup-safi: "In case of MPLS or SR-MPLS, an 'IP/UDP Payload
PseudoWire' label for GTP is encoded in an Extended Community..."
Use the MUP Extended Community (type 0x0c) for label signaling.

AFI/SAFI: IPv4 (1) or IPv6 (2) / MUP (69)

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#mup-draft-mpmz-bess-mup-safi

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

# Every MUP should be imported from this file
# as it makes sure that all the registering decorator are run

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.nlri.mup.nlri import MUP

from exabgp.bgp.message.update.nlri.mup.isd import InterworkSegmentDiscoveryRoute
from exabgp.bgp.message.update.nlri.mup.dsd import DirectSegmentDiscoveryRoute
from exabgp.bgp.message.update.nlri.mup.t1st import Type1SessionTransformedRoute
from exabgp.bgp.message.update.nlri.mup.t2st import Type2SessionTransformedRoute

__all__ = [
    'MUP',
    'InterworkSegmentDiscoveryRoute',
    'DirectSegmentDiscoveryRoute',
    'Type1SessionTransformedRoute',
    'Type2SessionTransformedRoute',
]
