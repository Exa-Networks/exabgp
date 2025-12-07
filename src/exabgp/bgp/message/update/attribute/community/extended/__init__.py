"""extended/__init__.py

BGP Extended Communities (Attribute Code 16).

Reference: RFC 4360 - BGP Extended Communities Attribute
           https://datatracker.ietf.org/doc/html/rfc4360

Extended Community Format (8 bytes):
+-----------------------------------+
|    Type (1 octet)                 |  High bit: 0=IANA, 1=transitive
+-----------------------------------+
|    Sub-Type (1 octet)             |
+-----------------------------------+
|    Value (6 octets)               |
+-----------------------------------+

Common Extended Community Types:
| Type | Sub | Name                    | Class                |
|------|-----|-------------------------|----------------------|
| 0x00 | 0x02| Route Target (2-byte)   | RouteTargetASN2Number|
| 0x01 | 0x02| Route Target (IPv4)     | RouteTargetIPNumber  |
| 0x02 | 0x02| Route Target (4-byte)   | RouteTargetASN4Number|
| 0x00 | 0x03| Route Origin            | OriginASNIP          |
| 0x03 | 0x0c| Encapsulation           | Encapsulation        |
| 0x06 | 0x00| MAC Mobility (EVPN)     | MacMobility          |
| 0x06 | 0x04| ESI Label (EVPN)        | -                    |
| 0x80 | 0x06| FlowSpec Traffic Rate   | TrafficRate          |
| 0x80 | 0x07| FlowSpec Traffic Action | TrafficAction        |
| 0x80 | 0x08| FlowSpec Redirect       | TrafficRedirect      |
| 0x80 | 0x09| FlowSpec Traffic Mark   | TrafficMark          |
| 0x0c | -   | MUP Extended Community  | MUPExtendedCommunity |

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#extended-community-rfc-4360

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Every Extended Community should be imported from this file
# as it makes sure that all the registering decorator are run

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.attribute.community.extended.community import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended.community import ExtendedCommunityIPv6
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunities
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunitiesIPv6

from exabgp.bgp.message.update.attribute.community.extended.l2info import L2Info
from exabgp.bgp.message.update.attribute.community.extended.origin import Origin
from exabgp.bgp.message.update.attribute.community.extended.origin import OriginASNIP
from exabgp.bgp.message.update.attribute.community.extended.origin import OriginIPASN
from exabgp.bgp.message.update.attribute.community.extended.origin import OriginASN4Number
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTarget
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN2Number
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetIPNumber
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN4Number
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRate
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficAction
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRedirect
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRedirectASN4
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficMark
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRedirectIPv6
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficNextHopIPv4IETF
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficNextHopIPv6IETF
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficNextHopSimpson
from exabgp.bgp.message.update.attribute.community.extended.encapsulation import Encapsulation
from exabgp.bgp.message.update.attribute.community.extended.chso import ConsistentHashSortOrder
from exabgp.bgp.message.update.attribute.community.extended.rt_record import RTRecord
from exabgp.bgp.message.update.attribute.community.extended.flowspec_scope import InterfaceSet
from exabgp.bgp.message.update.attribute.community.extended.mac_mobility import MacMobility
from exabgp.bgp.message.update.attribute.community.extended.mup import MUPExtendedCommunity

__all__ = [
    'ExtendedCommunity',
    'ExtendedCommunityIPv6',
    'ExtendedCommunities',
    'ExtendedCommunitiesIPv6',
    'L2Info',
    'Origin',
    'OriginASNIP',
    'OriginIPASN',
    'OriginASN4Number',
    'RouteTarget',
    'RouteTargetASN2Number',
    'RouteTargetIPNumber',
    'RouteTargetASN4Number',
    'TrafficRate',
    'TrafficAction',
    'TrafficRedirect',
    'TrafficRedirectASN4',
    'TrafficMark',
    'TrafficRedirectIPv6',
    'TrafficNextHopIPv4IETF',
    'TrafficNextHopIPv6IETF',
    'TrafficNextHopSimpson',
    'Encapsulation',
    'ConsistentHashSortOrder',
    'RTRecord',
    'InterfaceSet',
    'MacMobility',
    'MUPExtendedCommunity',
]
