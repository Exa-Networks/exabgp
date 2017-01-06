"""
node/__init__.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2016 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

from exabgp.bgp.message.update.attribute.bgpls.node.nodename import NodeName
from exabgp.bgp.message.update.attribute.bgpls.node.isisarea import IsisArea
from exabgp.bgp.message.update.attribute.bgpls.node.nodeflags import NodeFlags
from exabgp.bgp.message.update.attribute.bgpls.node.opaque import NodeOpaque
from exabgp.bgp.message.update.attribute.bgpls.node.lterid import LocalTeRid


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
