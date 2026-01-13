"""bgpls/__init__.py

BGP-LS Attribute (Attribute Code 29).

Reference: RFC 7752 - North-Bound Distribution of Link-State and TE Information Using BGP
           https://datatracker.ietf.org/doc/html/rfc7752
           RFC 9552 - Distribution of Link-State and TE Information Using BGP (obsoletes 7752)
           https://datatracker.ietf.org/doc/html/rfc9552
           RFC 9514 - Segment Routing Extensions for BGP-LS
           https://datatracker.ietf.org/doc/html/rfc9514
Registry:  https://www.iana.org/assignments/bgp-ls-parameters

BGP-LS Attribute TLV Format:
+-----------------------------------+
|    Type (2 octets)                |
+-----------------------------------+
|    Length (2 octets)              |
+-----------------------------------+
|    Value (variable)               |
+-----------------------------------+

Attribute Categories and TLV Ranges:
- Node Attributes:   TLVs 1024-1029, 1034-1035 (node/)
- Link Attributes:   TLVs 1030-1031, 1088-1100, 1106-1108, 1162, 1250, 1252 (link/)
- Prefix Attributes: TLVs 1152-1158, 1170-1171 (prefix/)

See subdirectory __init__.py files for complete TLV-to-class mapping tables:
- node/__init__.py   - 8 TLVs implemented
- link/__init__.py   - 22 TLVs implemented
- prefix/__init__.py - 9 TLVs implemented

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#bgp-ls-attribute-tlvs-rfc-7752

Created by Evelio Vila 2016-12-01
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

from exabgp.bgp.message.update.attribute.bgpls.link.igpmetric import IgpMetric
from exabgp.bgp.message.update.attribute.bgpls.link.srlg import Srlg
from exabgp.bgp.message.update.attribute.bgpls.link.mplsmask import MplsMask
from exabgp.bgp.message.update.attribute.bgpls.link.temetric import TeMetric
from exabgp.bgp.message.update.attribute.bgpls.node.localrouterid import LocalRouterId
from exabgp.bgp.message.update.attribute.bgpls.link.remoterouterid import RemoteRouterId
from exabgp.bgp.message.update.attribute.bgpls.link.admingroup import AdminGroup
from exabgp.bgp.message.update.attribute.bgpls.link.maxbw import MaxBw
from exabgp.bgp.message.update.attribute.bgpls.link.maxreservablebw import MaxReservableBw
from exabgp.bgp.message.update.attribute.bgpls.link.unreservedbw import UnreservedBw
from exabgp.bgp.message.update.attribute.bgpls.link.protection import LinkProtectionType
from exabgp.bgp.message.update.attribute.bgpls.link.opaque import LinkOpaque
from exabgp.bgp.message.update.attribute.bgpls.link.linkname import LinkName
from exabgp.bgp.message.update.attribute.bgpls.node.nodename import NodeName
from exabgp.bgp.message.update.attribute.bgpls.node.isisarea import IsisArea
from exabgp.bgp.message.update.attribute.bgpls.node.nodeflags import NodeFlags
from exabgp.bgp.message.update.attribute.bgpls.node.opaque import NodeOpaque
from exabgp.bgp.message.update.attribute.bgpls.prefix.igpflags import IgpFlags
from exabgp.bgp.message.update.attribute.bgpls.prefix.igpextags import IgpExTags
from exabgp.bgp.message.update.attribute.bgpls.prefix.igptags import IgpTags
from exabgp.bgp.message.update.attribute.bgpls.prefix.opaque import PrefixOpaque
from exabgp.bgp.message.update.attribute.bgpls.prefix.ospfaddr import OspfForwardingAddress
from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixmetric import PrefixMetric
from exabgp.bgp.message.update.attribute.bgpls.node.srcap import SrCapabilities
from exabgp.bgp.message.update.attribute.bgpls.node.sralgo import SrAlgorithm
from exabgp.bgp.message.update.attribute.bgpls.link.adjacencysid import AdjacencySid
from exabgp.bgp.message.update.attribute.bgpls.link.lanadjacencysid import LanAdjacencySid
from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixattributesflags import PrefixAttributesFlags
from exabgp.bgp.message.update.attribute.bgpls.prefix.sourcerouterid import SourceRouterId
from exabgp.bgp.message.update.attribute.bgpls.link.delaymetric import DelayMetric
from exabgp.bgp.message.update.attribute.bgpls.link.localremoteid import LinkLocalRemoteIdentifiers