# encoding: utf-8
"""
generic.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.notification import Notify

from exabgp.protocol.family import AFI,SAFI
from exabgp.bgp.message.update.nlri.path import PathPrefix
from exabgp.bgp.message.update.nlri.mpls import MPLS
from exabgp.bgp.message.update.nlri.flow import FlowNLRI
from exabgp.bgp.message.update.nlri.vpls import VPLSNLRI

from exabgp.util.od import od
from exabgp.logger import Logger,LazyFormat

logger = None

def NLRIFactory (afi,safi,bgp,has_multiple_path,nexthop,action):
	global logger
	if logger is None:
		logger = Logger()
	logger.parser(LazyFormat("parsing %s/%s nlri payload " % (afi,safi),od,bgp))

	if safi in (SAFI.unicast, SAFI.multicast, SAFI.nlri_mpls, SAFI.mpls_vpn):
		if afi in (AFI.ipv4, AFI.ipv6):
			return PathPrefix.unpack(afi,safi,bgp,has_multiple_path,nexthop,action)
		raise Notify(3,0,'invalid family for inet')

	if safi in (SAFI.nlri_mpls, SAFI.mpls_vpn):
		if afi in (AFI.ipv4, AFI.ipv6):
			return MPLS.unpack(afi,safi,bgp,has_multiple_path,nexthop,action)
		raise Notify(3,0,'invalid family for mpls')

	if safi in (SAFI.flow_ip,SAFI.flow_vpn):
		if afi in (AFI.ipv4, AFI.ipv6):
			return FlowNLRI.unpack(afi,safi,nexthop,bgp,action)
		raise Notify(3,0,'invalid family for flowspec')

	if safi in (SAFI.vpls,):
		if afi in (AFI.l2vpn,):
			return VPLSNLRI.unpack(afi,safi,nexthop,bgp,action)
		raise Notify(3,0,'invalid family for vpls')

	# if afi == AFI.ipv4:
	# 	if safi == SAFI.rtc:
	# 		return RouteTargetConstraint.unpack(afi,safi,bgp)
	#	raise Notify(3,0,'invalid family for VPLSNLRI')

	raise Notify(3,0,'Unexpcted family received %s/%s' % (afi,safi))
