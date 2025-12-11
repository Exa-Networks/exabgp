"""node/__init__.py

BGP-LS Node Attribute TLVs.

Reference: RFC 7752 Section 3.3.1 - Node Attribute TLVs
           https://tools.ietf.org/html/rfc7752#section-3.3.1
           RFC 9514 - Segment Routing Extensions for BGP-LS
           https://datatracker.ietf.org/doc/html/rfc9514
Registry:  https://www.iana.org/assignments/bgp-ls-parameters

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#node-attribute-tlvs

TLV Code to Class Mapping (IANA Registry):
+------+----------------------------------+----------------------+
| TLV  | IANA/RFC Name                    | ExaBGP Class         |
+------+----------------------------------+----------------------+
| 1024 | Node Flag Bits                   | NodeFlags            |
| 1025 | Opaque Node Attribute            | NodeOpaque           |
| 1026 | Node Name                        | NodeName             |
| 1027 | IS-IS Area Identifier            | IsisArea             |
| 1028 | IPv4 Router-ID of Local Node     | LocalRouterId        |
| 1029 | IPv6 Router-ID of Local Node     | LocalRouterId        |
| 1034 | SR Capabilities                  | SrCapabilities       |
| 1035 | SR Algorithm                     | SrAlgorithm          |
+------+----------------------------------+----------------------+

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

#   +-------------+----------------------+----------+-------------------+
#   |   TLV Code  | Description          |   Length | Reference         |
#   |    Point    |                      |          | (RFC/Section)     |
#   +-------------+----------------------+----------+-------------------+
#   |     263     | Multi-Topology       | variable | Section 3.2.1.5   |
#   |             | Identifier           |          |                   |
#   |     1024    | Node Flag Bits       |        1 | Section 3.3.1.1   |
#   |     1025    | Opaque Node          | variable | Section 3.3.1.5   |
#   |             | Attribute            |          |                   |
#   |     1026    | Node Name            | variable | Section 3.3.1.3   |
#   |     1027    | IS-IS Area           | variable | Section 3.3.1.2   |
#   |             | Identifier           |          |                   |
#   |     1028    | IPv4 Router-ID of    |        4 | [RFC5305]/4.3     |
#   |             | Local Node           |          |                   |
#   |     1029    | IPv6 Router-ID of    |       16 | [RFC6119]/4.1     |
#   |             | Local Node           |          |                   |
#   +-------------+----------------------+----------+-------------------+
#   https://tools.ietf.org/html/rfc7752#section-3.3.1 - Node Attribute TLVs

from exabgp.bgp.message.update.attribute.bgpls.node.nodename import NodeName
from exabgp.bgp.message.update.attribute.bgpls.node.isisarea import IsisArea
from exabgp.bgp.message.update.attribute.bgpls.node.nodeflags import NodeFlags
from exabgp.bgp.message.update.attribute.bgpls.node.opaque import NodeOpaque
from exabgp.bgp.message.update.attribute.bgpls.node.localrouterid import LocalRouterId

# draft-gredler-idr-bgp-ls-segment-routing-ext-03 extensions
#      +----------------+-----------------+----------+---------------+
#      | TLV Code Point | Description     | Length   |       Section |
#      +----------------+-----------------+----------+---------------+
#      |      1034      | SR Capabilities | variable | Section 2.1.1 |
#      |      1035      | SR Algorithm    | variable | Section 2.1.2 |
#      +----------------+-----------------+----------+---------------+

from exabgp.bgp.message.update.attribute.bgpls.node.srcap import SrCapabilities
from exabgp.bgp.message.update.attribute.bgpls.node.sralgo import SrAlgorithm
