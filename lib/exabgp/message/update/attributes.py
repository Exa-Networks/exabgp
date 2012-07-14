# encoding: utf-8
"""
set.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
"""

from exabgp.structure.address import AFI,SAFI
from exabgp.structure.asn import AS_TRANS
from exabgp.message.update.attribute import AttributeID

from exabgp.message.update.attribute.origin      import Origin
from exabgp.message.update.attribute.aspath      import ASPath,AS4Path
from exabgp.message.update.attribute.localpref   import LocalPreference
from exabgp.message.update.attribute                  import AttributeID
from exabgp.message.update.attribute.atomicaggregate  import AtomicAggregate

# =================================================================== Attributes

class MultiAttributes (list):
	def __init__ (self,attribute):
		list.__init__(self)
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
		return 'MultiAttibutes(%s)' % ' '.join(str(_) for _ in self)

	def __repr__ (self):
		return str(self)

class Attributes (dict):
	cache = {
		# There can only be one :)
		AttributeID.ATOMIC_AGGREGATE : { '' : AtomicAggregate() }
	}

	autocomplete = True

	def __init__ (self):
		self._str = ''

	def has (self,k):
		return self.has_key(k)

	def get (self,attributeid,data):
		if data in self.cache.setdefault(attributeid,{}):
			self.add(self.cache[attributeid][data])
			return True
		return False

	def add (self,attribute,data=None):
		self._str = ''
		if data:
			self.cache[attribute.ID][data] = attribute
		if attribute.MULTIPLE:
			if self.has(attribute.ID):
				self[attribute.ID].append(attribute)
			else:
				self[attribute.ID] = MultiAttributes(attribute)
		else:
			self[attribute.ID] = attribute

	def remove (self,attrid):
		self.pop(attrid)

	def _as_path (self,asn4,asp):
		message = ''
		# if the peer does not understand ASN4, we need to build a transitive AS4_PATH
		if not asn4:
			has_asn4 = False
			aspath = ASPath(False,asp.asptype)
			as4path = AS4Path(asp.asptype)
			for segment in asp.aspsegment:
				if segment.asn4():
					has_asn4 = True
					aspath.add(AS_TRANS)
					as4path.add(segment)
				else:
					aspath.add(segment)
					as4path.add(segment)
			message += aspath.pack()
			if has_asn4:
				message += as4path.pack()
		else:
			message += ASPath(True,asp.asptype,asp.aspsegment).pack()
		return message

	def bgp_announce (self,asn4,local_asn,peer_asn):
		ibgp = (local_asn == peer_asn)
		# we do not store or send MED
		message = ''

		if AttributeID.ORIGIN in self:
			message += self[AttributeID.ORIGIN].pack()
		elif self.autocomplete:
			message += Origin(Origin.IGP).pack()

		if AttributeID.AS_PATH in self:
			asp = self[AttributeID.AS_PATH]
			message += self._as_path(asn4,asp)
		elif self.autocomplete:
			if ibgp:
				asp = ASPath(asn4,ASPath.AS_SEQUENCE,[])
			else:
				asp = ASPath(asn4,ASPath.AS_SEQUENCE,[local_asn])
			message += self._as_path(asn4,asp)
		else:
			raise RuntimeError('Generated routes must always have an AS_PATH ')

		if AttributeID.NEXT_HOP in self:
			afi = self[AttributeID.NEXT_HOP].afi
			safi = self[AttributeID.NEXT_HOP].safi
			if afi == AFI.ipv4 and safi in [SAFI.unicast, SAFI.multicast]:
				message += self[AttributeID.NEXT_HOP].pack()

		if AttributeID.MED in self:
			if local_asn != peer_asn:
				message += self[AttributeID.MED].pack()

		if ibgp:
			if AttributeID.LOCAL_PREF in self:
				message += self[AttributeID.LOCAL_PREF].pack()
			else:
				# '\x00\x00\x00d' is 100 packed in long network bytes order
				message += LocalPreference('\x00\x00\x00d').pack()

		# This generate both AGGREGATOR and AS4_AGGREGATOR
		if AttributeID.AGGREGATOR in self:
			aggregator = self[AttributeID.AGGREGATOR]
			message += aggregator.pack(asn4)

		for attribute in [AttributeID.ATOMIC_AGGREGATE,AttributeID.COMMUNITY,AttributeID.ORIGINATOR_ID,AttributeID.CLUSTER_LIST,AttributeID.EXTENDED_COMMUNITY]:
			if attribute in self:
				message += self[attribute].pack()

		return message

	def __str__ (self):
		if self._str:
			return self._str

		next_hop = ''
		if self.has(AttributeID.NEXT_HOP):
			next_hop = ' next-hop %s' % str(self[AttributeID.NEXT_HOP]).lower()

		origin = ''
		if self.has(AttributeID.ORIGIN):
			origin = ' origin %s' % str(self[AttributeID.ORIGIN]).lower()

		aspath = ''
		if self.has(AttributeID.AS_PATH):
			aspath = ' %s' % str(self[AttributeID.AS_PATH]).lower().replace('_','-')

		local_pref = ''
		if self.has(AttributeID.LOCAL_PREF):
			local_pref = ' local-preference %s' % self[AttributeID.LOCAL_PREF]

		aggregator = ''
		if self.has(AttributeID.AGGREGATOR):
			aggregator = ' aggregator ( %s )' % self[AttributeID.AGGREGATOR]

		atomic = ''
		if self.has(AttributeID.ATOMIC_AGGREGATE):
			atomic = ' atomic-aggregate'

		med = ''
		if self.has(AttributeID.MED):
			med = ' med %s' % self[AttributeID.MED]

		communities = ''
		if self.has(AttributeID.COMMUNITY):
			communities = ' community %s' % str(self[AttributeID.COMMUNITY])

		originator_id = ''
		if self.has(AttributeID.ORIGINATOR_ID):
			originator_id = ' originator-id %s' % str(self[AttributeID.ORIGINATOR_ID])

		cluster_list = ''
		if self.has(AttributeID.ORIGINATOR_ID):
			cluster_list = ' cluster-list %s' % str(self[AttributeID.ORIGINATOR_ID])

		ecommunities = ''
		if self.has(AttributeID.EXTENDED_COMMUNITY):
			ecommunities = ' extended-community %s' % str(self[AttributeID.EXTENDED_COMMUNITY])

		mpr = ''
		if self.has(AttributeID.MP_REACH_NLRI):
			mpr = ' mp_reach_nlri %s' % str(self[AttributeID.MP_REACH_NLRI])

		self._str = "%s%s%s%s%s%s%s%s%s%s%s%s" % (next_hop,origin,aspath,local_pref,atomic,aggregator,med,communities,ecommunities,mpr,originator_id,cluster_list)
		return self._str

	def __repr__ (self):
		return str(self)
