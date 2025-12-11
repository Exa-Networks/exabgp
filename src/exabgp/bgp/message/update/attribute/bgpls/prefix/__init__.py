"""prefix/__init__.py

BGP-LS Prefix Attribute TLVs.

Reference: RFC 7752 Section 3.3.3 - Prefix Attribute TLVs
           https://tools.ietf.org/html/rfc7752#section-3.3.3
           RFC 9514 - Segment Routing Extensions for BGP-LS
           https://datatracker.ietf.org/doc/html/rfc9514
Registry:  https://www.iana.org/assignments/bgp-ls-parameters

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#prefix-attribute-tlvs

TLV Code to Class Mapping (IANA Registry):
+------+----------------------------------+----------------------+
| TLV  | IANA/RFC Name                    | ExaBGP Class         |
+------+----------------------------------+----------------------+
| 1152 | IGP Flags                        | IgpFlags             |
| 1153 | IGP Route Tag                    | IgpTags              |
| 1154 | IGP Extended Route Tag           | IgpExTags            |
| 1155 | Prefix Metric                    | PrefixMetric         |
| 1156 | OSPF Forwarding Address          | OspfForwardingAddress|
| 1157 | Opaque Prefix Attribute          | PrefixOpaque         |
| 1158 | Prefix-SID                       | PrefixSid            |
| 1170 | Prefix Attributes Flags          | PrefixAttributesFlags|
| 1171 | Source Router Identifier         | SourceRouterId       |
+------+----------------------------------+----------------------+

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

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

from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixattributesflags import PrefixAttributesFlags
from exabgp.bgp.message.update.attribute.bgpls.prefix.sourcerouterid import SourceRouterId
