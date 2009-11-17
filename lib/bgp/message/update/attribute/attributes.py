#!/usr/bin/env python
# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.message.inet import new_NLRI
from bgp.message.update.attribute.parent import Attribute,Flag

from bgp.message.update.attribute.origin      import *	# 01
from bgp.message.update.attribute.aspath      import *	# 02
from bgp.message.update.attribute.nexthop     import *	# 03
from bgp.message.update.attribute.med         import * 	# 04
from bgp.message.update.attribute.localpref   import *	# 05
from bgp.message.update.attribute.aggregate   import *	# 06
from bgp.message.update.attribute.aggregator  import *	# 07
from bgp.message.update.attribute.communities import *	# 08
# 09
# 10 - 0A
# 11 - 0B
# 12 - 0C
# 13 - 0D
from bgp.message.update.attribute.mprnlri     import *	# 14 - 0E
from bgp.message.update.attribute.mpurnlri    import *	# 15 - 0F


# =================================================================== Attributes

def new_Attributes (data):
	attributes = Attributes()
	attributes.new(data)
	return attributes

class Attributes (dict):
	def has (self,k):
		return self.has_key(k)

	def add (self,attribute):
		if self.has(attribute.ID):
			if attribute.MULTIPLE:
				self[attribute.ID].append(attribute)
				return True
			return False
		else:
			if attribute.MULTIPLE:
				self[attribute.ID] = [attribute]
			else:
				self[attribute.ID] = attribute
			return True

	def new (self,data):
		try:
			return self._new(data)
		except IndexError:
			raise
			raise Notify(3,2,data)

	def _new (self,data):
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
			return self.new(data[length:])

		if code == Attribute.ORIGIN:
			self.add(new_Origin(data))
			return self.new(data[length:])

		if code == Attribute.AS_PATH:
			self.add(new_ASPath(data))
			return self.new(data[length:])

		if code == Attribute.NEXT_HOP:
			self.add(new_NextHop(data[:4]))
			return self.new(data[length:])

		if code == Attribute.MULTI_EXIT_DISC:
			self.add(new_MED(data))
			return self.new(data[length:])

		if code == Attribute.LOCAL_PREFERENCE:
			self.add(new_LocalPreference(data))
			return self.new(data[length:])

		if code == Attribute.ATOMIC_AGGREGATE:
			# ignore
			return self.new(data[length:])

		if code == Attribute.AGGREGATOR:
			# content is 6 bytes
			return self.new(data[length:])

		if code == Attribute.COMMUNITY:
			self.add(new_Communities(data))
			return self.new(data[length:])

		if code == Attribute.MP_UNREACH_NLRI:
			next_attributes = data[length:]
			data = data[:length]
			afi,safi = unpack('!HB',data[:3])
			offset = 3
			# XXX: See RFC 5549 for better support
			if not afi in (AFI.ipv4,AFI.ipv6) or safi != SAFI.unicast:
				print 'we only understand IPv4/IPv6 and should never have received this route (%s %s)' % (afi,safi)
				return self.new(next_attributes)
			data = data[offset:]
			while data:
				route = to_Update(NLRIS(), new_NLRI(data,afi))
				data = data[len(route.nlri):]
				self.add(MPURNLRI(route))
				print 'removing MP route %s' % str(route)
			return self.new(next_attributes)

		if code == Attribute.MP_REACH_NLRI:
			next_attributes = data[length:]
			data = data[:length]
			afi,safi = unpack('!HB',data[:3])
			offset = 3
			if not afi in (AFI.ipv4,AFI.ipv6) or safi != SAFI.unicast:
				print 'we only understand IPv4/IPv6 and should never have received this route (%s %s)' % (afi,safi)
				return self.new(next_attributes)
			len_nh = ord(data[offset])
			offset += 1
			if afi == AFI.ipv4 and not len_nh != 4:
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				print 'bad IPv4 next-hop length (%d)' % len_nh
				return self.new(next_attributes)
			if afi == AFI.ipv6 and not len_nh in (16,32):
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				print 'bad IPv6 next-hop length (%d)' % len_nh
				return self.new(next_attributes)
			nh = data[offset:offset+len_nh]
			offset += len_nh
			if len_nh == 32:
				# we have a link-local address in the next-hop we ideally need to ignore
				if nh[0] == 0xfe: nh = nh[16:]
				elif nh[16] == 0xfe: nh = nh[:16]
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				else: self(next_attributes)
			nh = socket.inet_ntop(socket.AF_INET6 if len_nh >= 16 else socket.AF_INET,nh)
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
				route = to_Update(NLRIS(), new_NLRI(data,afi))
				route.next_hop6 = nh
				data = data[len(route.nlri):]
				self.add(MPRNLRI(route))
				print 'adding MP route %s' % str(route)
			return self.new(next_attributes)

		import warnings
		warnings.warn("Could not parse attribute %s" % str(code))
		return self.new(data[length:])




from bgp.message.update.update import Update, to_Update, NLRIS
