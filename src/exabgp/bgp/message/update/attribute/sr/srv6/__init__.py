"""srv6/__init__.py

SRv6 Service TLVs for BGP Prefix-SID Attribute.

Reference: RFC 9252 - BGP Overlay Services Based on Segment Routing over IPv6 (SRv6)
           https://datatracker.ietf.org/doc/html/rfc9252

SRv6 SID Information Sub-TLV Format:
+-----------------------------------+
|    SRv6 SID (16 octets)           |
+-----------------------------------+
|    SID Flags (1 octet)            |
+-----------------------------------+
|    Endpoint Behavior (2 octets)   |
+-----------------------------------+
|    Sub-Sub-TLVs (variable)        |
+-----------------------------------+

TLV Types:
- Type 5: SRv6 L3 Service TLV - Srv6L3Service
- Type 6: SRv6 L2 Service TLV - Srv6L2Service
- SRv6 SID Information Sub-TLV - Srv6SidInformation
- SRv6 SID Structure Sub-Sub-TLV - Srv6SidStructure

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#segment-routing-attributes

Created by Ryoga Saito 2022-02-24
Copyright (c) 2022 Ryoga Saito. All rights reserved.
"""

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.attribute.sr.srv6.l2service import Srv6L2Service
from exabgp.bgp.message.update.attribute.sr.srv6.l3service import Srv6L3Service
from exabgp.bgp.message.update.attribute.sr.srv6.sidinformation import Srv6SidInformation
from exabgp.bgp.message.update.attribute.sr.srv6.sidstructure import Srv6SidStructure
