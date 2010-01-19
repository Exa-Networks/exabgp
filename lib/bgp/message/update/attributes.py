#!/usr/bin/env python
# encoding: utf-8
"""
set.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from bgp.message.update.attribute import Attribute

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

class MultiAttributes (list):
	def __init__ (self,attribute):
		self.ID = attribute.ID
		self.FLAG = attribute.FLAG
		self.MULTIPLE = True
		self.append(attribute)

	def pack (self):
		r = []
		for attribute in self:
			r.append(attribute.pack())
		return ''.join(r)

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MultiAttribute"

class Attributes (dict):
	autocomplete = True
	
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
				self[attribute.ID] = MultiAttributes(attribute)
			else:
				self[attribute.ID] = attribute
			return True

	def bgp (self,local_asn,peer_asn):
		ibgp = local_asn == peer_asn
		# we do not store or send MED
		message = ''

		attributes = [self[a].ID for a in self]

		if Attribute.ORIGIN in self:
			message += self[Attribute.ORIGIN].pack()
		elif self.autocomplete:
			message += Origin(Origin.IGP).pack()

		if Attribute.AS_PATH in self:
			message += self[Attribute.AS_PATH].pack()
		elif self.autocomplete:
			if local_asn == peer_asn:
				message += ASPath(ASPath.AS_SEQUENCE,[]).pack()
			else:
				message += ASPath(ASPath.AS_SEQUENCE,[local_asn]).pack()

		if Attribute.NEXT_HOP in self:
			if self[Attribute.NEXT_HOP].attribute.afi == AFI.ipv4:
				message += self[Attribute.NEXT_HOP].pack()
			else:
				message += MPRNLRI(self.afi,self.safi,self).pack()

		if Attribute.LOCAL_PREFERENCE in self:
			if local_asn == peer_asn:
				message += self[Attribute.LOCAL_PREFERENCE].pack()

		if Attribute.MULTI_EXIT_DISC in self:
			if local_asn != peer_asn:
				message += self[Attribute.MULTI_EXIT_DISC].pack()

		for attribute in [Communities.ID,MPURNLRI.ID,MPRNLRI.ID]:
			if  self.has(attribute):
				message += self[attribute].pack()

		return message

	def __str__ (self):
		next_hop = ''
		if self.has(Attribute.NEXT_HOP):
			next_hop = ' next-hop %s' % str(self[Attribute.NEXT_HOP].attribute).lower()

		origin = ''
		if self.has(Attribute.ORIGIN):
			origin = ' origin %s' % str(self[Attribute.ORIGIN]).lower()

		aspath = ''
		if self.has(Attribute.AS_PATH):
			aspath = ' %s' % str(self[Attribute.AS_PATH]).lower().replace('_','-')

		local_pref= ''
		if self.has(Attribute.LOCAL_PREFERENCE):
			l = self[Attribute.LOCAL_PREFERENCE]
			local_pref= ' local_preference %s' % l

		med = ''
		if self.has(Attribute.MULTI_EXIT_DISC):
			m = self[Attribute.MULTI_EXIT_DISC]
			med = ' med %s' % m

		communities = ''
		if self.has(Attribute.COMMUNITY):
			communities = ' community %s' % str(self[Attribute.COMMUNITY])

		return "%s%s%s%s%s%s" % (next_hop,origin,aspath,local_pref,med,communities)

