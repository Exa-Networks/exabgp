# encoding: utf-8
"""
attribute/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Every Attribute should be imported from this file
# as it makes sure that all the registering decorator are run

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.attributes import Attributes
from exabgp.bgp.message.update.attribute.generic import GenericAttribute
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.attribute.aspath import ASPath
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
