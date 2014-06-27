# encoding: utf-8
"""
generic.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.notification import Notify

from struct import unpack
from exabgp.protocol.family import AFI,SAFI
from exabgp.bgp.message.update.nlri.bgp import NLRI,PathInfo,Labels,RouteDistinguisher,mask_to_bytes
from exabgp.bgp.message.update.nlri.flow import FlowNLRI,decode,factory,CommonOperator
from exabgp.bgp.message.update.nlri.vpls import VPLSNLRI
#from exabgp.bgp.message.update.nlri.mpls import VPNLabelledPrefix,RouteTargetConstraint

from exabgp.bgp.message.update.attribute.nexthop import NextHop

from exabgp.bgp.message.direction import IN

from exabgp.util.od import od
from exabgp.logger import Logger,LazyFormat

logger = None

def NLRIFactory (afi,safi,bgp,has_multiple_path,nexthop,action):
	if safi in (SAFI.unicast_multicast, SAFI.unicast, SAFI.multicast, SAFI.nlri_mpls, SAFI.mpls_vpn):
		if afi in (AFI.ipv4, AFI.ipv6):
			return _NLRIFactory(afi,safi,bgp,has_multiple_path,nexthop,action)
		raise Notify(3,0,'invalid family for inet/mpls')

	if safi in (SAFI.flow_ip,SAFI.flow_vpn):
		if afi in (AFI.ipv4, AFI.ipv6):
			return _FlowNLRIFactory(afi,safi,nexthop,bgp,action)
		raise Notify(3,0,'invalid family for flowspec')

	if safi in (SAFI.vpls,):
		if afi in (AFI.l2vpn,):
			return _VPLSNLRIFactory(afi,safi,nexthop,bgp,action)
		raise Notify(3,0,'invalid family for vpls')

	# if afi == AFI.ipv4:
	# 	if safi == SAFI.rtc:
	# 		return RouteTargetConstraint.unpack(afi,safi,bgp)
	#	raise Notify(3,0,'invalid family for VPLSNLRI')

	raise Notify(3,0,'Unexpcted family received %s/%s' % (afi,safi))


def _nlri_parser (afi,safi,bgp,action):
	labels = []
	rd = ''

	mask = ord(bgp[0])
	bgp = bgp[1:]

	if SAFI(safi).has_label():
		while bgp and mask >= 8:
			label = int(unpack('!L',chr(0) + bgp[:3])[0])
			bgp = bgp[3:]
			mask -= 24  	# 3 bytes
			# The last 4 bits are the bottom of Stack
			# The last bit is set for the last label
			labels.append(label>>4)
			# This is a route withdrawal
			if label == 0x800000 and action == IN.withdrawn:
				break
			# This is a next-hop
			if label == 0x000000:
				break
			if label & 1:
				break

	if SAFI(safi).has_rd():
		mask -= 8*8  # the 8 bytes of the route distinguisher
		rd = bgp[:8]
		bgp = bgp[8:]

	if mask < 0:
		raise Notify(3,10,'invalid length in NLRI prefix')

	if not bgp and mask:
		raise Notify(3,10,'not enough data for the mask provided to decode the NLRI')

	size = mask_to_bytes.get(mask,None)
	if size is None:
		raise Notify(3,10,'invalid netmask found when decoding NLRI')

	if len(bgp) < size:
		raise Notify(3,10,'could not decode route with AFI %d sand SAFI %d' % (afi,safi))

	network,bgp = bgp[:size],bgp[size:]
	padding = '\0'*(NLRI.length[afi]-size)
	prefix = network + padding

	return labels,rd,mask,size,prefix,bgp

def _VPLSNLRIFactory(afi,safi,nexthop,bgp,action):
	global logger
	if logger is None:
		logger = Logger()
	logger.parser(LazyFormat("parsing l2vpn nlri payload ",od,bgp))
	nlri = VPLSNLRI.unpack(bgp)
	nlri.action = action
	nlri.nexthop = NextHop.unpack(nexthop)
	return len(bgp), nlri


def _FlowNLRIFactory (afi,safi,nexthop,bgp,action):
	global logger
	if logger is None:
		logger = Logger()
	logger.parser(LazyFormat("parsing flow nlri payload ",od,bgp))

	total = len(bgp)
	length,bgp = ord(bgp[0]),bgp[1:]

	if length & 0xF0 == 0xF0:  # bigger than 240
		extra,bgp = ord(bgp[0]),bgp[1:]
		length = ((length & 0x0F) << 16) + extra

	if length > len(bgp):
		raise Notify(3,10,'invalid length at the start of the the flow')

	bgp = bgp[:length]
	nlri = FlowNLRI(afi,safi)
	nlri.action = action

	if nexthop:
		nlri.nexthop = NextHop.unpack(nexthop)

	if safi == SAFI.flow_vpn:
		nlri.rd = RouteDistinguisher(bgp[:8])
		bgp = bgp[8:]

	seen = []

	while bgp:
		what,bgp = ord(bgp[0]),bgp[1:]

		if what not in decode.get(afi,{}):
			raise Notify(3,10,'unknown flowspec component received for address family %d' % what)

		seen.append(what)
		if sorted(seen) != seen:
			raise Notify(3,10,'components are not sent in the right order %s' % seen)

		decoder = decode[afi][what]
		klass = factory[afi][what]

		if decoder == 'prefix':
			if afi == AFI.ipv4:
				_,rd,mask,size,prefix,left = _nlri_parser(afi,safi,bgp,action)
				adding = klass(prefix,mask)
				if not nlri.add(adding):
					raise Notify(3,10,'components are incompatible (two sources, two destinations, mix ipv4/ipv6) %s' % seen)
				logger.parser(LazyFormat("added flow %s (%s) payload " % (klass.NAME,adding),od,bgp[:-len(left)]))
				bgp = left
			else:
				byte,bgp = bgp[1],bgp[0]+bgp[2:]
				offset = ord(byte)
				_,rd,mask,size,prefix,left = _nlri_parser(afi,safi,bgp,action)
				adding = klass(prefix,mask,offset)
				if not nlri.add(adding):
					raise Notify(3,10,'components are incompatible (two sources, two destinations, mix ipv4/ipv6) %s' % seen)
				logger.parser(LazyFormat("added flow %s (%s) payload " % (klass.NAME,adding),od,bgp[:-len(left)]))
				bgp = left
		else:
			end = False
			while not end:
				byte,bgp = ord(bgp[0]),bgp[1:]
				end = CommonOperator.eol(byte)
				operator = CommonOperator.operator(byte)
				length = CommonOperator.length(byte)
				value,bgp = bgp[:length],bgp[length:]
				adding = klass.decoder(value)
				nlri.add(klass(operator,adding))
				logger.parser(LazyFormat("added flow %s (%s) operator %d len %d payload " % (klass.NAME,adding,byte,length),od,value))

	return total-len(bgp),nlri

def _NLRIFactory (afi,safi,bgp,has_multiple_path,nexthop,action):
	if has_multiple_path:
		path_identifier = bgp[:4]
		bgp = bgp[4:]
		length = 4
	else:
		path_identifier = ''
		length = 0

	labels,rd,mask,size,prefix,left = _nlri_parser(afi,safi,bgp,action)

	nlri = NLRI(afi,safi,prefix,mask,NextHop.unpack(nexthop),action)

	if path_identifier:
		nlri.path_info = PathInfo(packed=path_identifier)
	if labels:
		nlri.labels = Labels(labels)
	if rd:
		nlri.rd = RouteDistinguisher(rd)

	return length + len(bgp) - len(left),nlri
