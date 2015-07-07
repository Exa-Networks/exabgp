# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import collections
from struct import unpack

from exabgp.configuration.environment import environment

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.generic import GenericAttribute
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.attribute.aspath import ASPath
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.community.communities import Communities
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunities

from exabgp.bgp.message.notification import Notify

from exabgp.logger import Logger
from exabgp.logger import LazyAttribute


class _NOTHING (object):
	def pack (self, _=None):
		return ''

NOTHING = _NOTHING()


# =================================================================== Attributes
#

# 0                   1
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |  Attr. Flags  |Attr. Type Code|
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

class Attributes (dict):
	MULTIPLE = (
		Attribute.CODE.MP_REACH_NLRI,
		Attribute.CODE.MP_UNREACH_NLRI,
	)
	NO_GENERATION = (
		Attribute.CODE.NEXT_HOP,
		Attribute.CODE.INTERNAL_SPLIT,
		Attribute.CODE.INTERNAL_WATCHDOG,
		Attribute.CODE.INTERNAL_WITHDRAW,
		Attribute.CODE.INTERNAL_NAME,
	)

	# A cache of parsed attributes
	cache = {}

	# The previously parsed Attributes
	cached = None
	# previously parsed attribute, from which cached was made of
	previous = ''

	representation = {
		# key:  (how, default, name, text_presentation, json_presentation),
		Attribute.CODE.ORIGIN:             ('string',  '', 'origin',             '%s',     '%s'),
		Attribute.CODE.AS_PATH:            ('multiple','', ('as-path','as-set','confederation-path','confederation-set'), '%s',     '%s'),
		Attribute.CODE.NEXT_HOP:           ('string',  '', 'next-hop',           '%s',     '%s'),
		Attribute.CODE.MED:                ('integer', '', 'med',                '%s',     '%s'),
		Attribute.CODE.LOCAL_PREF:         ('integer', '', 'local-preference',   '%s',     '%s'),
		Attribute.CODE.ATOMIC_AGGREGATE:   ('boolean', '', 'atomic-aggregate',   '%s',     '%s'),
		Attribute.CODE.AGGREGATOR:         ('string',  '', 'aggregator',         '( %s )', '%s'),
		Attribute.CODE.AS4_AGGREGATOR:     ('string',  '', 'aggregator',         '( %s )', '%s'),
		Attribute.CODE.COMMUNITY:          ('list',    '', 'community',          '%s',     '%s'),
		Attribute.CODE.ORIGINATOR_ID:      ('inet',    '', 'originator-id',      '%s',     '%s'),
		Attribute.CODE.CLUSTER_LIST:       ('list',    '', 'cluster-list',       '%s',     '%s'),
		Attribute.CODE.EXTENDED_COMMUNITY: ('list',    '', 'extended-community', '%s',     '%s'),
		Attribute.CODE.PMSI_TUNNEL:        ('string',  '', 'pmsi',               '%s',     '%s'),
		Attribute.CODE.AIGP:               ('integer', '', 'aigp',               '%s',     '%s'),
		Attribute.CODE.INTERNAL_NAME:      ('string',  '', 'name',               '%s',     '%s'),
	}

	def _generate_text (self):
		for code in sorted(self.keys()):
			# XXX: FIXME: really we should have a INTERNAL attribute in the classes
			if code in Attributes.NO_GENERATION:
				continue
			attribute = self[code]
			if code not in self.representation or attribute.GENERIC:
				if code in self.MULTIPLE:
					for attr in attribute:
						yield ' attribute [ 0x%02X 0x%02X %s ]' % (code,attr.FLAG,str(attr))
				else:
					yield ' attribute [ 0x%02X 0x%02X %s ]' % (code,attribute.FLAG,str(attribute))
			else:
				how, _, name, presentation, __ = self.representation[code]
				if how == 'boolean':
					yield ' %s' % name
				elif how == 'list':
					yield ' %s %s' % (name, presentation % str(attribute))
				elif how == 'multiple':
					yield ' %s %s' % (name[0], presentation % str(attribute))
				else:
					yield ' %s %s' % (name, presentation % str(attribute))

	def _generate_json (self):
		for code in sorted(self.keys()):
			# remove the next-hop from the attribute as it is define with the NLRI
			if code in Attributes.NO_GENERATION:
				continue
			attribute = self[code]
			if code in self.representation:
				how, _, name, __, presentation = self.representation[code]
				if how == 'boolean':
					yield '"%s": %s' % (name, 'true' if self.has(code) else 'false')
				elif how == 'string':
					yield '"%s": "%s"' % (name, presentation % str(attribute))
				elif how == 'list':
					yield '"%s": %s' % (name, presentation % attribute.json())
				elif how == 'multiple':
					for n in name:
						value = attribute.json(n)
						if value:
							yield '"%s": %s' % (n, presentation % value)
				elif how == 'inet':
					yield '"%s": "%s"' % (name, presentation % str(attribute))
				# Should never be ran
				else:
					yield '"%s": %s' % (name, presentation % str(attribute))
			else:
				if code in Attributes.MULTIPLE:
					for attr in attribute:
						yield '"attribute-0x%02X-0x%02X": "%s"' % (code,attr.FLAG,str(attr))
				else:
					yield '"attribute-0x%02X-0x%02X": "%s"' % (code,attribute.FLAG,str(attribute))

	def __init__ (self):
		# cached representation of the object
		self._str = ''
		self._idx = ''
		self._json = ''
		# The parsed attributes have no mp routes and/or those are last
		self.cacheable = True

		# XXX: FIXME: surely not the best place for this
		Attribute.caching = environment.settings().cache.attributes

	def has (self, k):
		return k in self

	def add (self, attribute, _=None):
		# we return None as attribute if the unpack code must not generate them
		if attribute is None:
			return

		self._str = ''
		self._json = ''

		# XXX: FIXME: I am not sure anymore that more than one of each is possible
		if attribute.ID in Attributes.MULTIPLE:
			# deadcode: setdefault does not seem to exist anywhere ? (TM)
			self.setdefault(attribute.ID,[]).append(attribute)
		# elif attribute.ID in (Attribute.CODE.COMMUNITY, Attribute.CODE.EXTENDED_COMMUNITY):
		# 	if attribute.ID not in self:
		# 		self[attribute.ID] = Attribute.klass(attribute.ID,attribute.FLAG)()
		# 	self[attribute.ID].add(attribute)
		elif attribute.ID in self:
			# For flows we can add extended-communities using special keywords and extended-community
			# This allows this trick
			if attribute.ID != Attribute.CODE.EXTENDED_COMMUNITY:
				raise Notify(3,0,'multiple attribute for %s' % str(Attribute.CODE(attribute.ID)))
			for community in attribute.communities:
				self[attribute.ID].add(community)
		else:
			self[attribute.ID] = attribute

	def remove (self, attrid):
		self.pop(attrid)

	def watchdog (self):
		return self.pop(Attribute.CODE.INTERNAL_WATCHDOG,None)

	def withdraw (self):
		return self.pop(Attribute.CODE.INTERNAL_WITHDRAW,None) is not None

	def pack (self, negotiated, with_default=True):
		local_asn = negotiated.local_as
		peer_asn = negotiated.peer_as

		message = ''

		default = {
			Attribute.CODE.ORIGIN: lambda l,r: Origin(Origin.IGP),
			Attribute.CODE.AS_PATH: lambda l,r: ASPath([],[]) if l == r else ASPath([local_asn,],[]),
			Attribute.CODE.LOCAL_PREF: lambda l,r: LocalPreference(100) if l == r else NOTHING,
		}

		skip = {
			Attribute.CODE.NEXT_HOP: lambda l,r,nh: nh.ipv4() is not True,
			Attribute.CODE.LOCAL_PREF: lambda l,r,nh: l != r,
		}

		keys = self.keys()
		alls = set(keys + default.keys() if with_default else [])

		for code in sorted(alls):
			if code in (
				Attribute.CODE.INTERNAL_SPLIT,
				Attribute.CODE.INTERNAL_WATCHDOG,
				Attribute.CODE.INTERNAL_WITHDRAW,
				Attribute.CODE.INTERNAL_NAME
			):
				continue

			if code not in keys and code in default:
				message += default[code](local_asn,peer_asn).pack(negotiated)
				continue

			attribute = self[code]

			if code in skip and skip[code](local_asn,peer_asn,attribute):
				continue

			if code in Attributes.MULTIPLE:
				for attr in attribute:
					message += attr.pack(negotiated)
			else:
				message += attribute.pack(negotiated)

		return message

	def json (self):
		if not self._json:
			self._json = ', '.join(self._generate_json())
		return self._json

	def __repr__ (self):
		if not self._str:
			self._str = ''.join(self._generate_text())
		return self._str

	def index (self):
		# XXX: something a little bit smaller memory wise ?
		if not self._idx:
			idx = ''.join(self._generate_text())
			nexthop = str(self.get(Attribute.CODE.NEXT_HOP,''))
			self._idx = '%s next-hop %s' % (idx,nexthop) if nexthop else idx
		return self._idx

	@classmethod
	def unpack (cls, data, negotiated):
		try:
			if cls.cached:
				if data == cls.previous:
					return cls.cached
				# # This code may mess with the cached data
				# elif cls.previous and data.startswith(cls.previous):
				# 	attributes = Attributes()
				# 	for key in cls.cached:
				# 		attributes[key] = cls.cached[key]
				# 	attributes.parse(data[len(cls.previous):],negotiated)
				else:
					attributes = cls().parse(data,negotiated)
			else:
				attributes = cls().parse(data,negotiated)

			if Attribute.CODE.AS_PATH in attributes and Attribute.CODE.AS4_PATH in attributes:
				attributes.merge_attributes()

			if Attribute.CODE.MP_REACH_NLRI not in attributes and Attribute.CODE.MP_UNREACH_NLRI not in attributes:
				cls.previous = data
				cls.cached = attributes
			else:
				cls.previous = ''
				cls.cached = None

			return attributes
		except IndexError:
			raise Notify(3,2,data)

	@staticmethod
	def flag_attribute_content (data):
		flag = Attribute.Flag(ord(data[0]))
		attr = Attribute.CODE(ord(data[1]))

		if flag & Attribute.Flag.EXTENDED_LENGTH:
			length = unpack('!H',data[2:4])[0]
			return flag, attr, data[4:length+4]
		else:
			length = ord(data[2])
			return flag, attr, data[3:length+3]

	def parse (self, data, negotiated):
		if not data:
			return self

		# We do not care if the attribute are transitive or not as we do not redistribute
		flag = Attribute.Flag(ord(data[0]))
		aid = Attribute.CODE(ord(data[1]))

		if flag & Attribute.Flag.EXTENDED_LENGTH:
			length = unpack('!H',data[2:4])[0]
			offset = 4
		else:
			length = ord(data[2])
			offset = 3

		data = data[offset:]
		left = data[length:]
		attribute = data[:length]

		logger = Logger()
		logger.parser(LazyAttribute(flag,aid,length,data[:length]))

		# remove the PARTIAL bit before comparaison if the attribute is optional
		if aid in Attribute.attributes_optional:
			flag &= Attribute.Flag.MASK_PARTIAL & 0xFF
			# flag &= ~Attribute.Flag.PARTIAL & 0xFF  # cleaner than above (python use signed integer for ~)

		# handle the attribute if we know it
		if Attribute.registered(aid,flag):
			self.add(Attribute.unpack(aid,flag,attribute,negotiated))
			return self.parse(left,negotiated)
		# XXX: FIXME: we could use a fallback function here like capability

		# if we know the attribute but the flag is not what the RFC says. ignore it.
		if aid in Attribute.attributes_known:
			logger.parser('invalid flag for attribute %s (flag 0x%02X, aid 0x%02X)' % (Attribute.CODE.names.get(aid,'unset'),flag,aid))
			return self.parse(left,negotiated)

		# it is an unknown transitive attribute we need to pass on
		if flag & Attribute.Flag.TRANSITIVE:
			logger.parser('unknown transitive attribute (flag 0x%02X, aid 0x%02X)' % (flag,aid))
			self.add(GenericAttribute(aid,flag | Attribute.Flag.PARTIAL,attribute),attribute)
			return self.parse(left,negotiated)

		# it is an unknown non-transitive attribute we can ignore.
		logger.parser('ignoring unknown non-transitive attribute (flag 0x%02X, aid 0x%02X)' % (flag,aid))
		return self.parse(left,negotiated)

	def merge_attributes (self):
		as2path = self[Attribute.CODE.AS_PATH]
		as4path = self[Attribute.CODE.AS4_PATH]
		self.remove(Attribute.CODE.AS_PATH)
		self.remove(Attribute.CODE.AS4_PATH)

		# this key is unique as index length is a two header, plus a number of ASN of size 2 or 4
		# so adding the: make the length odd and unique
		key = "%s:%s" % (as2path.index, as4path.index)

		# found a cache copy
		cached = Attribute.cache.get(Attribute.CODE.AS_PATH,{}).get(key,None)
		if cached:
			self.add(cached,key)
			return

		# as_seq = []
		# as_set = []

		len2 = len(as2path.as_seq)
		len4 = len(as4path.as_seq)

		# RFC 4893 section 4.2.3
		if len2 < len4:
			as_seq = as2path.as_seq
		else:
			as_seq = as2path.as_seq[:-len4]
			as_seq.extend(as4path.as_seq)

		len2 = len(as2path.as_set)
		len4 = len(as4path.as_set)

		if len2 < len4:
			as_set = as4path.as_set
		else:
			as_set = as2path.as_set[:-len4]
			as_set.extend(as4path.as_set)

		aspath = ASPath(as_seq,as_set)
		self.add(aspath,key)

	def __hash__ (self):
		# XXX: FIXME: not excellent... :-(
		# FIXME: two routes with distinct nh but other attributes equal
		#        will hash to the same value until repr represents the nh (??)
		return hash(repr(self))

	# BaGPipe code ..

	# test that sets of attributes exactly match
	# can't rely on __eq__ for this, because __eq__ relies on Attribute.__eq__ which does not look at attributes values

	def sameValuesAs (self, other):
		# we sort based on packed values since the items do not
		# necessarily implement __cmp__
		def sorter (x, y):
			return cmp(x.pack(), y.pack())

		try:
			for key in set(self.iterkeys()).union(set(other.iterkeys())):
				if (key == Attribute.CODE.MP_REACH_NLRI or key == Attribute.CODE.MP_UNREACH_NLRI):
					continue

				sval = self[key]
				oval = other[key]

				# In the case where the attribute is Communities or
				# extended communities, we want to compare values independently of their order
				if isinstance(sval, Communities):
					if not isinstance(oval, Communities):
						return False

					sval = sorted(sval,sorter)
					oval = sorted(oval,sorter)

				if cmp(sval,oval) != 0:
					return False
			return True
		except KeyError:
			return False
