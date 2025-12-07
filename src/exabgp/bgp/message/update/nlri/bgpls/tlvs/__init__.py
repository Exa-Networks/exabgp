"""bgpls/tlvs/__init__.py

BGP-LS TLV (Type-Length-Value) Descriptor Components.

Reference: RFC 7752 - North-Bound Distribution of Link-State and TE Information Using BGP
           https://datatracker.ietf.org/doc/html/rfc7752

These TLVs are building blocks used within BGP-LS NLRI to describe
network topology elements (nodes, links, prefixes).

TLV Format (RFC 7752 Section 3.1):
+-----------------------------------+
|    Type (2 octets)                |
+-----------------------------------+
|    Length (2 octets)              |
+-----------------------------------+
|    Value (variable)               |
+-----------------------------------+

Node Descriptor TLVs (Section 3.2.1.4):
- Type 512: Autonomous System - NodeDescriptor
- Type 513: BGP-LS Identifier - NodeDescriptor
- Type 514: OSPF Area-ID - NodeDescriptor
- Type 515: IGP Router-ID - NodeDescriptor

Link Descriptor TLVs (Section 3.2.2):
- Type 258: Link Local/Remote Identifiers - LinkIdentifier
- Type 259: IPv4 Interface Address - IfaceAddr
- Type 260: IPv4 Neighbor Address - NeighAddr
- Type 261: IPv6 Interface Address - IfaceAddr
- Type 262: IPv6 Neighbor Address - NeighAddr

Prefix Descriptor TLVs (Section 3.2.3):
- Type 264: Multi-Topology Identifier
- Type 265: OSPF Route Type - OspfRoute
- Type 266: IP Reachability Information - IpReach

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#bgp-ls-rfc-7752--rfc-9552

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor
from exabgp.bgp.message.update.nlri.bgpls.tlvs.neighaddr import NeighAddr
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ifaceaddr import IfaceAddr
from exabgp.bgp.message.update.nlri.bgpls.tlvs.linkid import LinkIdentifier
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ipreach import IpReach
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ospfroute import OspfRoute
