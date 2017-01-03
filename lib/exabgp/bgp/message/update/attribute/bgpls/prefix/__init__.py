"""
prefix/__init__.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2016 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

from exabgp.bgp.message.update.attribute.bgpls.prefix.igpflags import IgpFlags
from exabgp.bgp.message.update.attribute.bgpls.prefix.igpextags import IgpExTags
from exabgp.bgp.message.update.attribute.bgpls.prefix.igptags import IgpTags
from exabgp.bgp.message.update.attribute.bgpls.prefix.opaque import PrefixOpaque
from exabgp.bgp.message.update.attribute.bgpls.prefix.ospfaddr import OspfForwardingAddress
from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixmetric import PrefixMetric

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
