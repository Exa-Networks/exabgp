#!/usr/bin/env python
# encoding: utf-8
"""
parser.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from struct import unpack

from bgp.structure.afi import AFI
from bgp.structure.safi import SAFI
from bgp.message.update.attribute.flag import Flag
from bgp.message.update.attribute import Attribute
from bgp.message.update.attributes import Attributes

from bgp.message.update.attribute.origin      import *	# 01
from bgp.message.update.attribute.aspath      import *	# 02
from bgp.message.update.attribute.nexthop     import *	# 03
from bgp.message.update.attribute.med         import * 	# 04
from bgp.message.update.attribute.localpref   import *	# 05
from bgp.message.update.attribute.aggregate   import *	# 06
from bgp.message.update.attribute.aggregator  import *	# 07
from bgp.message.update.attribute.communities import *	# 08

# =================================================================== Attributes

def new_Attributes (data):
	try:
		parser = Parser()
		parser.parse(data)
		return parser.attributes
	except IndexError:
		raise Notify(3,2,data)

class Parser (object):
	def __init__ (self):
		self.attributes = Attributes()
	
	def parse (self,data):
		if not data:
			return self

		# We do not care if the attribute are transitive or not as we do not redistribute
		flag = Flag(ord(data[0]))
		code = Attribute(ord(data[1]))

		if flag & Flag.EXTENDED_LENGTH:
			length = unpack('!H',data[2:4])[0]
			offset = 4
		else:
			length = ord(data[2])
			offset = 3

		data = data[offset:]

		if not length:
			return self.parse(data[length:])

		if code == Attribute.ORIGIN:
			self.attributes.add(new_Origin(data))
			return self.parse(data[length:])

		if code == Attribute.AS_PATH:
			self.attributes.add(new_ASPath(data))
			return self.parse(data[length:])

		if code == Attribute.NEXT_HOP:
			self.attributes.add(new_NextHop(data[:4]))
			return self.parse(data[length:])

		if code == Attribute.MULTI_EXIT_DISC:
			self.attributes.add(new_MED(data))
			return self.parse(data[length:])

		if code == Attribute.LOCAL_PREFERENCE:
			self.attributes.add(new_LocalPreference(data))
			return self.parse(data[length:])

		if code == Attribute.ATOMIC_AGGREGATE:
			# ignore
			return self.parse(data[length:])

		if code == Attribute.AGGREGATOR:
			# content is 6 bytes
			return self.parse(data[length:])

		if code == Attribute.COMMUNITY:
			self.attributes.add(new_Communities(data))
			return self.parse(data[length:])

		if code == Attribute.MP_UNREACH_NLRI:
			next_attributes = data[length:]
			data = data[:length]
			afi,safi = unpack('!HB',data[:3])
			offset = 3
			# XXX: See RFC 5549 for better support
			if not afi in (AFI.ipv4,AFI.ipv6) or safi != SAFI.unicast:
				print 'we only understand IPv4/IPv6 and should never have received this route (%s %s)' % (afi,safi)
				return self.parse(next_attributes)
			data = data[offset:]
			while data:
				route = BGPPrefix(afi,data)
				data = data[len(route):]
				# XXX: we need to create one route per NLRI and then attribute them
				#self.attributes.add(MPURNLRI(AFI(afi),SAFI(safi),route))
				print 'removing MP route %s' % str(route)
			return self.parse(next_attributes)

		if code == Attribute.MP_REACH_NLRI:
			next_attributes = data[length:]
			data = data[:length]
			afi,safi = unpack('!HB',data[:3])
			offset = 3
			if not afi in (AFI.ipv4,AFI.ipv6) or safi != SAFI.unicast:
				print 'we only understand IPv4/IPv6 and should never have received this route (%s %s)' % (afi,safi)
				return self.parse(next_attributes)
			len_nh = ord(data[offset])
			offset += 1
			if afi == AFI.ipv4 and not len_nh != 4:
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				print 'bad IPv4 next-hop length (%d)' % len_nh
				return self.parse(next_attributes)
			if afi == AFI.ipv6 and not len_nh in (16,32):
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				print 'bad IPv6 next-hop length (%d)' % len_nh
				return self.parse(next_attributes)
			nh = data[offset:offset+len_nh]
			offset += len_nh
			if len_nh == 32:
				# we have a link-local address in the next-hop we ideally need to ignore
				if nh[0] == 0xfe: nh = nh[16:]
				elif nh[16] == 0xfe: nh = nh[:16]
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				else: self(next_attributes)
			if len_nh >= 16: nh = socket.inet_ntop(socket.AF_INET6,nh)
			else: nh = socket.inet_ntop(socket.AF_INET,nh)
			nb_snpa = ord(data[offset])
			offset += 1
			snpas = []
			for i in range(nb_snpa):
				len_snpa = ord(offset)
				offset += 1
				snpas.append(data[offset:offset+len_snpa])
				offset += len_snpa
			data = data[offset:]
			while data:
				route = BGPPrefix(afi,data)
				data = data[len(route):]
				# XXX: we are not storing the NextHop Anymore
				#route.next_hop = nh
				#self.attributes.add(MPRNLRI(AFI(afi),SAFI(safi),route))
				print 'adding MP route %s' % str(route)
			return self.parse(next_attributes)

		import warnings
		warnings.warn("Could not parse attribute %s %s" % (str(code),[hex(ord(_)) for _ in data]))
		return self.parse(data[length:])

