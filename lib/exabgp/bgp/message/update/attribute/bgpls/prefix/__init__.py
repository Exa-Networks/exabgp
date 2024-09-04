"""
prefix/__init__.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

#  +---------------+----------------------+----------+-----------------+
#  |    TLV Code   | Description          |   Length | Reference       |
#  |     Point     |                      |          |                 |
#  +---------------+----------------------+----------+-----------------+
#  |      1152     | IGP Flags            |        1 | Section 3.3.3.1 |
#  |      1153     | IGP Route Tag        |      4*n | [RFC5130]       |
#  |      1154     | IGP Extended Route   |      8*n | [RFC5130]       |
#  |               | Tag                  |          |                 |
#  |      1155     | Prefix Metric        |        4 | [RFC5305]       |
#  |      1156     | OSPF Forwarding      |        4 | [RFC2328]       |
#  |               | Address              |          |                 |
#  |      1157     | Opaque Prefix        | variable | Section 3.3.3.6 |
#  |               | Attribute            |          |                 |
#  +---------------+----------------------+----------+-----------------+
#  https://tools.ietf.org/html/rfc7752#section-3.3.3
from exabgp.bgp.message.update.attribute.bgpls.prefix.igpflags import IgpFlags
from exabgp.bgp.message.update.attribute.bgpls.prefix.igpextags import IgpExTags
from exabgp.bgp.message.update.attribute.bgpls.prefix.igptags import IgpTags
from exabgp.bgp.message.update.attribute.bgpls.prefix.opaque import PrefixOpaque
from exabgp.bgp.message.update.attribute.bgpls.prefix.ospfaddr import OspfForwardingAddress
from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixmetric import PrefixMetric

# Segment routing extensions:
# draft-gredler-idr-bgp-ls-segment-routing-ext-03
#   +----------------+---------------------+----------+---------------+
#   | TLV Code Point | Description         |   Length | Section       |
#   +----------------+---------------------+----------+---------------+
#   |    1158    | Prefix SID              | variable | Section 2.3.1 |
#   |    1170    | IGP Prefix Attributes   | variable | Section 2.3.3 |
#   |    1171    | Source Router-ID        | variable | Section 2.3.4 |
#   |    1161    | SID/Label TLV           | variable | Section 2.3.7.2 |
# Note: Only IS-IS IGP extensions as defined in draft-ietf-isis-segment-routing-extensions
# are currently parsed by ExaBGP. Binding segments are not supported (3.5.  Binding Segment)
from exabgp.bgp.message.update.attribute.bgpls.prefix.srprefix import SrPrefix
from exabgp.bgp.message.update.attribute.bgpls.prefix.srigpprefixattr import SrIgpPrefixAttr
from exabgp.bgp.message.update.attribute.bgpls.prefix.srrid import SrSourceRouterID
