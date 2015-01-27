# encoding: utf-8
"""
attribute/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.attribute import Attribute
# from exabgp.bgp.message.update.attribute.generic import GenericAttribute
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.attribute.aspath import ASPath
from exabgp.bgp.message.update.attribute.aspath import AS4Path
from exabgp.bgp.message.update.attribute.nexthop import NextHop
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.atomicaggregate import AtomicAggregate
from exabgp.bgp.message.update.attribute.aggregator import Aggregator
from exabgp.bgp.message.update.attribute.aggregator import Aggregator4
from exabgp.bgp.message.update.attribute.community.communities import Communities
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunities
from exabgp.bgp.message.update.attribute.originatorid import OriginatorID
from exabgp.bgp.message.update.attribute.clusterlist import ClusterList
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
from exabgp.bgp.message.update.attribute.pmsi import PMSI
from exabgp.bgp.message.update.attribute.aigp import AIGP


Attribute.register_attribute(Origin)
Attribute.register_attribute(ASPath)
Attribute.register_attribute(AS4Path)
Attribute.register_attribute(NextHop)
Attribute.register_attribute(MED)
Attribute.register_attribute(LocalPreference)
Attribute.register_attribute(AtomicAggregate)
Attribute.register_attribute(Aggregator)
Attribute.register_attribute(Aggregator4)
Attribute.register_attribute(Communities)
Attribute.register_attribute(ExtendedCommunities)
Attribute.register_attribute(OriginatorID)
Attribute.register_attribute(ClusterList)
Attribute.register_attribute(MPRNLRI)
Attribute.register_attribute(MPURNLRI)
Attribute.register_attribute(PMSI)
Attribute.register_attribute(AIGP)
