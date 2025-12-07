"""sr/__init__.py

Segment Routing BGP Prefix-SID Attribute.

Reference: RFC 8669 - Segment Routing Prefix Segment Identifier Extensions for BGP
           https://datatracker.ietf.org/doc/html/rfc8669

Prefix-SID Attribute (Type 40) TLV Format:
+-----------------------------------+
|    TLV Type (1 octet)             |
+-----------------------------------+
|    TLV Length (2 octets)          |
+-----------------------------------+
|    TLV Value (variable)           |
+-----------------------------------+

TLV Types:
- Type 1: Label-Index TLV - SrLabelIndex
- Type 3: Originator SRGB TLV - SrGb
- Type 5: SRv6 L3 Service TLV (srv6/)
- Type 6: SRv6 L2 Service TLV (srv6/)

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#segment-routing-attributes

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.sr.labelindex import SrLabelIndex
from exabgp.bgp.message.update.attribute.sr.srgb import SrGb
