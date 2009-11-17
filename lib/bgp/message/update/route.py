#!/usr/bin/env python
# encoding: utf-8
"""
route.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.message.inet import AFI, SAFI, to_NLRI, new_NLRI, NLRI, to_IP, IP
from bgp.message.update.update import Update,NLRIS

#from bgp.message.update.attribute.parent import Attribute,Flag

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

# =================================================================== Route

def to_Route (ip,netmask):
	return Route(to_NLRI(ip,netmask))

def new_Route (data,afi):
	nlri = to_NLRI(data,afi)
	return Route(nlri)

class Route (object):
	def __init__ (self,nlri):
		self.nlri = nlri
		self.attributes = Attributes()

	def _set_next_hop (self,nh):
		self._next_hop = to_IP(nh)
	def _get_next_hop (self):
		return self._next_hop
	next_hop = property(_get_next_hop,_set_next_hop)

	def announce (self,local_asn,remote_asn):
		attributes = Attributes(self.attributes.copy())
		if self.nlri.afi == AFI.ipv4:
			attributes[Attribute.NEXT_HOP] = to_NextHop(self.next_hop.ip())
			return Update(NLRIS(),NLRIS([self.nlri]),attributes).announce(local_asn,remote_asn)
		if self.nlri.afi == AFI.ipv6:
			attributes[Attribute.NEXT_HOP] = to_NextHop('0.0.0.0')
			attributes[Attribute.MP_REACH_NLRI] = MPRNLRI(self)
			return Update(NLRIS(),NLRIS(),attributes).announce(local_asn,remote_asn)

	def update (self,local_asn,remote_asn):
		attributes = Attributes(self.attributes.copy())
		if self.nlri.afi == AFI.ipv4:
			attributes[Attribute.NEXT_HOP] = to_NextHop(self.next_hop)
		return Update(NLRIS(),NLRIS([self.nlri]),attributes).update(local_asn,remote_asn)

	def __str__ (self):
		local_pref= ''

		if self.attributes.has(Attribute.LOCAL_PREFERENCE):
			l = self.attributes[Attribute.LOCAL_PREFERENCE]
			if l == 100: # XXX: Double check default Local Pref
				local_pref= ' local_preference %s' % l

		communities = ''
		if self.attributes.has(Attribute.COMMUNITY):
			communities = ' community %s' % str(self.attributes[Attribute.COMMUNITY])

		next_hop = ''
		if self.attributes.has(Attribute.NEXT_HOP):
			next_hop = ' next-hop %s' % str(self.attributes[Attribute.NEXT_HOP])

		return "%s%s%s%s" % (self.nlri,next_hop,local_pref,communities)

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
				route = new_NLRI(data,afi)
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
				route = new_Route(data,afi)
				route.next_hop = nh
				data = data[len(route.nlri):]
				self.add(MPRNLRI(route))
				print 'adding MP route %s' % str(route)
			return self.new(next_attributes)

		import warnings
		warnings.warn("Could not parse attribute %s" % str(code))
		return self.new(data[length:])
