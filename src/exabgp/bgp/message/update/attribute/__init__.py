"""attribute/__init__.py

BGP Path Attributes Package.

Reference: RFC 4271 - A Border Gateway Protocol 4 (BGP-4)
           https://datatracker.ietf.org/doc/html/rfc4271

Path Attribute Header Format (RFC 4271 Section 4.3):
+-----------------------------------+
|    Attr. Flags (1 octet)          |
+-----------------------------------+
|    Attr. Type Code (1 octet)      |
+-----------------------------------+
|    Attr. Length (1 or 2 octets)   |
+-----------------------------------+
|    Attr. Value (variable)         |
+-----------------------------------+

Attribute Types:
| Code | Name               | Category           | Class            |
|------|--------------------|-------------------|------------------|
| 1    | ORIGIN             | Well-known Mand.  | Origin           |
| 2    | AS_PATH            | Well-known Mand.  | ASPath           |
| 3    | NEXT_HOP           | Well-known Mand.  | NextHop          |
| 4    | MULTI_EXIT_DISC    | Optional          | MED              |
| 5    | LOCAL_PREF         | Well-known Disc.  | LocalPreference  |
| 6    | ATOMIC_AGGREGATE   | Well-known Disc.  | AtomicAggregate  |
| 7    | AGGREGATOR         | Optional Trans.   | Aggregator       |
| 8    | COMMUNITY          | Optional Trans.   | Communities      |
| 9    | ORIGINATOR_ID      | Optional Non-Tr.  | OriginatorID     |
| 10   | CLUSTER_LIST       | Optional Non-Tr.  | ClusterList      |
| 14   | MP_REACH_NLRI      | Optional Non-Tr.  | MPRNLRI          |
| 15   | MP_UNREACH_NLRI    | Optional Non-Tr.  | MPURNLRI         |
| 16   | EXTENDED_COMMUNITY | Optional Trans.   | ExtendedCommunities |
| 22   | PMSI_TUNNEL        | Optional Trans.   | PMSI             |
| 26   | AIGP               | Optional Non-Tr.  | AIGP             |
| 29   | BGP-LS             | Optional Non-Tr.  | LinkState        |
| 32   | LARGE_COMMUNITY    | Optional Trans.   | LargeCommunities |
| 40   | PREFIX_SID         | Optional Trans.   | PrefixSid        |

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#path-attributes-rfc-4271

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Every Attribute should be imported from this file
# as it makes sure that all the registering decorator are run

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import Attributes, AttributeCollection, AttributesWire, AttributeSet
from exabgp.bgp.message.update.attribute.generic import GenericAttribute
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.attribute.aspath import ASPath
from exabgp.bgp.message.update.attribute.aspath import AS2Path
from exabgp.bgp.message.update.attribute.aspath import AS4Path
from exabgp.bgp.message.update.attribute.aspath import SET
from exabgp.bgp.message.update.attribute.aspath import SEQUENCE
from exabgp.bgp.message.update.attribute.aspath import CONFED_SET
from exabgp.bgp.message.update.attribute.aspath import CONFED_SEQUENCE
from exabgp.bgp.message.update.attribute.nexthop import NextHop
from exabgp.bgp.message.update.attribute.nexthop import NextHopSelf
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.atomicaggregate import AtomicAggregate
from exabgp.bgp.message.update.attribute.aggregator import Aggregator
from exabgp.bgp.message.update.attribute.aggregator import Aggregator4
from exabgp.bgp.message.update.attribute.community import Communities
from exabgp.bgp.message.update.attribute.community import LargeCommunities
from exabgp.bgp.message.update.attribute.community import ExtendedCommunities
from exabgp.bgp.message.update.attribute.originatorid import OriginatorID
from exabgp.bgp.message.update.attribute.clusterlist import ClusterList
from exabgp.bgp.message.update.attribute.clusterlist import ClusterID
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mprnlri import EMPTY_MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import EMPTY_MPURNLRI
from exabgp.bgp.message.update.attribute.pmsi import PMSI
from exabgp.bgp.message.update.attribute.aigp import AIGP
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid

__all__ = [
    'Attribute',
    'Attributes',
    'AttributeCollection',
    'AttributeSet',
    'AttributesWire',
    'GenericAttribute',
    'Origin',
    'ASPath',
    'AS2Path',
    'AS4Path',
    'SET',
    'SEQUENCE',
    'CONFED_SET',
    'CONFED_SEQUENCE',
    'NextHop',
    'NextHopSelf',
    'MED',
    'LocalPreference',
    'AtomicAggregate',
    'Aggregator',
    'Aggregator4',
    'Communities',
    'LargeCommunities',
    'ExtendedCommunities',
    'OriginatorID',
    'ClusterList',
    'ClusterID',
    'MPRNLRI',
    'EMPTY_MPRNLRI',
    'MPURNLRI',
    'EMPTY_MPURNLRI',
    'PMSI',
    'AIGP',
    'LinkState',
    'PrefixSid',
]
