"""
node/__init__.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

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
from exabgp.bgp.message.update.attribute.bgpls.node.lterid import LocalTeRid
from exabgp.bgp.message.update.attribute.bgpls.link.rterid import RemoteTeRid
from exabgp.bgp.message.update.attribute.bgpls.link.admingroup import AdminGroup
from exabgp.bgp.message.update.attribute.bgpls.link.maxbw import MaxBw
from exabgp.bgp.message.update.attribute.bgpls.link.rsvpbw import RsvpBw
from exabgp.bgp.message.update.attribute.bgpls.link.unrsvpbw import UnRsvpBw
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
from exabgp.bgp.message.update.attribute.bgpls.link.sradj import SrAdjacency
from exabgp.bgp.message.update.attribute.bgpls.link.sradjlan import SrAdjacencyLan
