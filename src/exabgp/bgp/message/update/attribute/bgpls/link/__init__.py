"""link/__init__.py

BGP-LS Link Attribute TLVs.

Reference: RFC 7752 Section 3.3.2 - Link Attribute TLVs
           https://tools.ietf.org/html/rfc7752#section-3.3.2
           RFC 9514 - Segment Routing Extensions for BGP-LS
           https://datatracker.ietf.org/doc/html/rfc9514
Registry:  https://www.iana.org/assignments/bgp-ls-parameters

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#link-attribute-tlvs

TLV Code to Class Mapping (IANA Registry):
+------+----------------------------------+----------------------+
| TLV  | IANA/RFC Name                    | ExaBGP Class         |
+------+----------------------------------+----------------------+
| 1030 | IPv4 Router-ID of Remote Node    | RemoteRouterId       |
| 1031 | IPv6 Router-ID of Remote Node    | RemoteRouterId       |
| 1088 | Administrative group (color)     | AdminGroup           |
| 1089 | Maximum link bandwidth           | MaxBw                |
| 1090 | Max. reservable link bandwidth   | MaxReservableBw      |
| 1091 | Unreserved bandwidth             | UnreservedBw         |
| 1092 | TE Default Metric                | TeMetric             |
| 1093 | Link Protection Type             | LinkProtectionType   |
| 1094 | MPLS Protocol Mask               | MplsMask             |
| 1095 | IGP Metric                       | IgpMetric            |
| 1096 | Shared Risk Link Group           | Srlg                 |
| 1097 | Opaque Link Attribute            | LinkOpaque           |
| 1098 | Link Name                        | LinkName             |
| 1099 | Adjacency SID                    | AdjacencySid         |
| 1100 | LAN Adjacency SID                | LanAdjacencySid      |
| 1038 | SRv6 Capabilities                | Srv6Capabilities     |
| 1106 | SRv6 End.X SID                   | Srv6EndX             |
| 1107 | IS-IS SRv6 LAN End.X SID         | Srv6LanEndXISIS      |
| 1108 | OSPFv3 SRv6 LAN End.X SID        | Srv6LanEndXOSPF      |
| 1162 | SRv6 Locator                     | Srv6Locator          |
| 1250 | SRv6 Endpoint Behavior           | Srv6EndpointBehavior |
| 1252 | SRv6 SID Structure               | Srv6SidStructure     |
+------+----------------------------------+----------------------+

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

#  +-----------+---------------------+--------------+------------------+
#  |  TLV Code | Description         |  IS-IS TLV   | Reference        |
#  |   Point   |                     |   /Sub-TLV   | (RFC/Section)    |
#  +-----------+---------------------+--------------+------------------+
#  |    1028   | IPv4 Router-ID of   |   134/---    | [RFC5305]/4.3    |
#  |           | Local Node          |              |                  |
#  |    1029   | IPv6 Router-ID of   |   140/---    | [RFC6119]/4.1    |
#  |           | Local Node          |              |                  |
#  |    1030   | IPv4 Router-ID of   |   134/---    | [RFC5305]/4.3    |
#  |           | Remote Node         |              |                  |
#  |    1031   | IPv6 Router-ID of   |   140/---    | [RFC6119]/4.1    |
#  |           | Remote Node         |              |                  |
#  |    1088   | Administrative      |     22/3     | [RFC5305]/3.1    |
#  |           | group (color)       |              |                  |
#  |    1089   | Maximum link        |     22/9     | [RFC5305]/3.4    |
#  |           | bandwidth           |              |                  |
#  |    1090   | Max. reservable     |    22/10     | [RFC5305]/3.5    |
#  |           | link bandwidth      |              |                  |
#  |    1091   | Unreserved          |    22/11     | [RFC5305]/3.6    |
#  |           | bandwidth           |              |                  |
#  |    1092   | TE Default Metric   |    22/18     | Section 3.3.2.3  |
#  |    1093   | Link Protection     |    22/20     | [RFC5307]/1.2    |
#  |           | Type                |              |                  |
#  |    1094   | MPLS Protocol Mask  |     ---      | Section 3.3.2.2  |
#  |    1095   | IGP Metric          |     ---      | Section 3.3.2.4  |
#  |    1096   | Shared Risk Link    |     ---      | Section 3.3.2.5  |
#  |           | Group               |              |                  |
#  |    1097   | Opaque Link         |     ---      | Section 3.3.2.6  |
#  |           | Attribute           |              |                  |
#  |    1098   | Link Name           |     ---      | Section 3.3.2.7  |
#   +-----------+---------------------+--------------+------------------+
#   https://tools.ietf.org/html/rfc7752#section-3.3.2 Link Attributes TLVs
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

#   +-----------+----------------------------+----------+---------------+
#   |  TLV Code | Description                |   Length |       Section |
#   |   Point   |                            |          |               |
#   +-----------+----------------------------+----------+---------------+
#   |    1099   | Adjacency Segment          | variable | Section 2.2.1 |
#   |           | Identifier (Adj-SID) TLV   |          |               |
#   |    1100   | LAN Adjacency Segment      | variable | Section 2.2.2 |
#   |           | Identifier (Adj-SID) TLV   |          |               |
#   +-----------+----------------------------+----------+---------------+
#   draft-gredler-idr-bgp-ls-segment-routing-ext-03
from exabgp.bgp.message.update.attribute.bgpls.link.adjacencysid import AdjacencySid
from exabgp.bgp.message.update.attribute.bgpls.link.lanadjacencysid import LanAdjacencySid

#  +================+=============================+===========+
#  | TLV Code Point | Description                 | Reference |
#  +================+=============================+===========+
#  | 1038           | SRv6 Capabilities TLV       | RFC 9514  |
#  | 1106           | SRv6 End.X SID TLV          | RFC 9514  |
#  | 1107           | SRv6 LAN End.X SID ISIS TLV | RFC 9514  |
#  | 1108           | SRv6 LAN End.X SID OSPF TLV | RFC 9514  |
#  | 1162           | SRv6 Locator TLV            | RFC 9514  |
#  | 1250           | SRv6 Endpoint Behavior TLV  | RFC 9514  |
#  | 1252           | SRv6 SID Structure TLV      | RFC 9514  |
#  +----------------+-----------------------------+-----------+
from exabgp.bgp.message.update.attribute.bgpls.link.srv6endx import Srv6EndX
from exabgp.bgp.message.update.attribute.bgpls.link.srv6sidstructure import Srv6SidStructure
from exabgp.bgp.message.update.attribute.bgpls.link.srv6capabilities import Srv6Capabilities
from exabgp.bgp.message.update.attribute.bgpls.link.srv6locator import Srv6Locator
from exabgp.bgp.message.update.attribute.bgpls.link.srv6endpointbehavior import Srv6EndpointBehavior
from exabgp.bgp.message.update.attribute.bgpls.link.srv6lanendx import Srv6LanEndXISIS, Srv6LanEndXOSPF

#  +================+===========================================+===========+
#  | TLV Code Point | Description                               | Reference |
#  +================+===========================================+===========+
#  | 1114           | Unidirectional Link Delay                 | RFC 8571  |
#  | 1115           | Min/Max Unidirectional Link Delay         | RFC 8571  |
#  | 1116           | Unidirectional Delay Variation            | RFC 8571  |
#  | 1117           | Unidirectional Link Loss                  | RFC 8571  |
#  | 1118           | Unidirectional Residual Bandwidth         | RFC 8571  |
#  | 1119           | Unidirectional Available Bandwidth        | RFC 8571  |
#  | 1120           | Unidirectional Utilized Bandwidth         | RFC 8571  |
#  +----------------+-------------------------------------------+-----------+
from exabgp.bgp.message.update.attribute.bgpls.link.delaymetric import (
    UnidirectionalLinkDelay,
    MinMaxUnidirectionalLinkDelay,
    UnidirectionalDelayVariation,
    UnidirectionalLinkLoss,
    UnidirectionalResidualBandwidth,
    UnidirectionalAvailableBandwidth,
    UnidirectionalUtilizedBandwidth,
)

#  +----------------+-------------------------------+-----------+
#  | TLV Code Point | Description                    | Reference |
#  +----------------+-------------------------------+-----------+
#  |  258           | Link Local/Remote Identifiers  | RFC 5307  |
#  +----------------+-------------------------------+-----------+
from exabgp.bgp.message.update.attribute.bgpls.link.localremoteid import LinkLocalRemoteIdentifiers
