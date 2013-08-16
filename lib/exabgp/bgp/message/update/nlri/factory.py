# encoding: utf-8
"""
generic.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.notification import Notify

from struct import unpack
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.update.nlri.bgp import NLRI,PathInfo,Labels,RouteDistinguisher,mask_to_bytes
from exabgp.bgp.message.update.nlri.flow import FlowNLRI,decode,factory,CommonOperator
from exabgp.bgp.message.update.attribute.nexthop import cachedNextHop

from exabgp.util.od import od
from exabgp.logger import Logger,LazyFormat

def NLRIFactory (afi,safi,bgp,has_multiple_path,nexthop,action):
	if safi in (133,134):
		return _FlowNLRIFactory(afi,safi,bgp)
	else:
		return _NLRIFactory(afi,safi,bgp,has_multiple_path,nexthop,action)

def _nlrifactory (afi,safi,bgp):
	labels = []
	rd = ''

	mask = ord(bgp[0])
	bgp = bgp[1:]

	if SAFI(safi).has_label():
		while bgp and mask >= 8:
			label = int(unpack('!L',chr(0) + bgp[:3])[0])
			bgp = bgp[3:]
			labels.append(label>>4)
			mask -= 24  # 3 bytes
			if label & 1:
				break
			# This is a route withdrawal, or next-hop
			if label == 0x000000 or label == 0x80000:
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

def _FlowNLRIFactory (afi,safi,bgp):
	logger = Logger()

	total = len(bgp)

	length,bgp = ord(bgp[0]),bgp[1:]

	if length & 0xF0 == 0xF0:  # bigger than 240
		extra,bgp = ord(bgp[0]),bgp[1:]
		length = ((length & 0x0F) << 16) + extra

	if length > len(bgp):
		raise Notify(3,10,'invalid length at the start of the the flow')

	bgp = bgp[:length]
	nlri = FlowNLRI(afi,safi)

	logger.parser(LazyFormat("parsing flow nlri payload ",od,bgp))

	seen = []

	while bgp:
		what,bgp = ord(bgp[0]),bgp[1:]

		if what not in decode:
			raise Notify(3,10,'unknown flowspec component received %d' % what)

		seen.append(what)
		if sorted(seen) != seen:
			raise Notify(3,10,'components are not sent in the right order %s' % seen)

		decoder = decode[what]
		klass = factory[what]

		if decoder == 'prefix':
			_,rd,mask,size,prefix,left = _nlrifactory(afi,safi,bgp)
			adding = klass(prefix,mask)
			nlri.add(adding)
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

	labels,rd,mask,size,prefix,left = _nlrifactory(afi,safi,bgp)

	nlri = NLRI(afi,safi,prefix,mask,cachedNextHop(nexthop),action)

	if path_identifier:
		nlri.path_info = PathInfo(packed=path_identifier)
	if labels:
		nlri.labels = Labels(labels)
	if rd:
		nlri.rd = RouteDistinguisher(rd)

	return length + len(bgp) - len(left),nlri
