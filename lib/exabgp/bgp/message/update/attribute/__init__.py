# encoding: utf-8
"""
attribute/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import collections
from struct import unpack

from exabgp.util.od import od
from exabgp.configuration.environment import environment

# Must be imported for the register API to work
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.generic import GenericAttribute
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.attribute.aspath import ASPath
from exabgp.bgp.message.update.attribute.nexthop import NextHop
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.atomicaggregate import AtomicAggregate
from exabgp.bgp.message.update.attribute.aggregator import Aggregator
from exabgp.bgp.message.update.attribute.community import Community
from exabgp.bgp.message.update.attribute.originatorid import OriginatorID
from exabgp.bgp.message.update.attribute.clusterlist import ClusterList
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
#from exabgp.bgp.message.update.attribute.community import Community
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.bgp.message.update.attribute.pmsi import PMSI
from exabgp.bgp.message.update.attribute.aigp import AIGP
# /forced import

from exabgp.bgp.message.notification import Notify

from exabgp.logger import Logger
from exabgp.logger import LazyFormat

class _NOTHING (object):
	def pack (self,negotiated=None):
		return ''

NOTHING = _NOTHING()

# ============================================================== MultiAttributes
#

# 0                   1
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |  Attr. Flags  |Attr. Type Code|
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


class MultiAttributes (list):
	def __init__ (self,attribute):
		list.__init__(self)
		self.ID = attribute.ID
		self.FLAG = attribute.FLAG
		self.MULTIPLE = True
		self.append(attribute)

	def pack (self,negotiated=None):
		r = []
		for attribute in self:
			r.append(attribute.pack())
		return ''.join(r)

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return '%s' % ' '.join(str(_) for _ in self)



# =================================================================== Attributes
#

class Attributes (dict):
	# A cache of parsed attributes
	cache = {}

	# The previously parsed Attributes
	cached = None
	# previously parsed attribute, from which cached was made of
	previous = ''

	representation = {
		#	key:  (how, default, name, text_presentation, json_presentation),
		Attribute.ID.ORIGIN             : ('string',  '', 'origin',             '%s',     '%s'),
		Attribute.ID.AS_PATH            : ('multiple','', ('as-path','as-set','confederation-path','confederation-set'), '%s',     '%s'),
		Attribute.ID.NEXT_HOP           : ('string',  '', 'next-hop',           '%s',     '%s'),
		Attribute.ID.MED                : ('integer', '', 'med',                '%s',     '%s'),
		Attribute.ID.LOCAL_PREF         : ('integer', '', 'local-preference',   '%s',     '%s'),
		Attribute.ID.ATOMIC_AGGREGATE   : ('boolean', '', 'atomic-aggregate',   '%s',     '%s'),
		Attribute.ID.AGGREGATOR         : ('string',  '', 'aggregator',         '( %s )', '%s'),
		Attribute.ID.AS4_AGGREGATOR     : ('string',  '', 'aggregator',         '( %s )', '%s'),
		Attribute.ID.COMMUNITY          : ('list',    '', 'community',          '%s',     '%s'),
		Attribute.ID.ORIGINATOR_ID      : ('inet',    '', 'originator-id',      '%s',     '%s'),
		Attribute.ID.CLUSTER_LIST       : ('list',    '', 'cluster-list',       '%s',     '%s'),
		Attribute.ID.EXTENDED_COMMUNITY : ('list',    '', 'extended-community', '%s',     '%s'),
		Attribute.ID.PMSI_TUNNEL        : ('string',  '', 'pmsi',               '%s',     '%s'),
		Attribute.ID.AIGP               : ('integer', '', 'aigp',               '%s',     '%s'),
		Attribute.ID.INTERNAL_NAME      : ('string',  '', 'name',               '%s',     '%s'),
	}

	def _generate_text (self,extra=None):
		exclude = [Attribute.ID.INTERNAL_SPLIT, Attribute.ID.INTERNAL_WATCHDOG, Attribute.ID.INTERNAL_WITHDRAW, Attribute.ID.NEXT_HOP]
		if extra:
			exclude.append(extra)
		for code in sorted(self.keys()):
			# XXX: FIXME: really we should have a INTERNAL attribute in the classes
			if code in exclude:
				continue
			if code in self.representation:
				how, default, name, presentation, _ = self.representation[code]
				if how == 'boolean':
					yield ' %s' % name
				elif how == 'list':
					yield ' %s %s' % (name, presentation % str(self[code]))
				elif how == 'multiple':
					yield ' %s %s' % (name[0], presentation % str(self[code]))
				else:
					yield ' %s %s' % (name, presentation % str(self[code]))
			else:
				yield ' attribute [ 0x%02X 0x%02X %s ]' % (code,self[code].FLAG,str(self[code]))

	def _generate_json (self):
		for code in sorted(self.keys() + [Attribute.ID.ATOMIC_AGGREGATE,]):
			# remove the next-hop from the attribute as it is define with the NLRI
			if code in (Attribute.ID.NEXT_HOP, Attribute.ID.INTERNAL_SPLIT, Attribute.ID.INTERNAL_WATCHDOG, Attribute.ID.INTERNAL_WITHDRAW):
				continue
			if code in self.representation:
				how, default, name, _, presentation = self.representation[code]
				if how == 'boolean':
					yield '"%s": %s' % (name, 'true' if self.has(code) else 'false')
				elif how == 'string':
					yield '"%s": "%s"' % (name, presentation % str(self[code]))
				elif how == 'list':
					yield '"%s": %s' % (name, presentation % self[code].json())
				elif how == 'multiple':
					for n in name:
						value = self[code].json(n)
						if value:
							yield '"%s": %s' % (n, presentation % value)
				elif how == 'inet':
					yield '"%s": "%s"' % (name, presentation % str(self[code]))
				# Should never be ran
				else:
					yield '"%s": %s' % (name, presentation % str(self[code]))
			else:
				yield '"attribute-0x%02X-0x%02X": "%s"' % (code,self[code].FLAG,str(self[code]))

	def __init__ (self):
		# cached representation of the object
		self._str = ''
		self._idx = ''
		self._json = ''
		# The parsed attributes have no mp routes and/or those are last
		self.cacheable = True

		# XXX: FIXME: surely not the best place for this
		Attribute.caching = environment.settings().cache.attributes

	def has (self,k):
		return k in self

	def add (self,attribute,data=None):
		# we return None as attribute if the unpack code must not generate them
		if attribute is None:
			return

		self._str = ''
		self._json = ''

		if attribute.MULTIPLE:
			if self.has(attribute.ID):
				self[attribute.ID].append(attribute)
			else:
				self[attribute.ID] = MultiAttributes(attribute)
		else:
			if attribute.ID in self:
				raise Notify(3,0,'multiple attribute for %s' % str(Attribute.ID(attribute.ID)))
			else:
				self[attribute.ID] = attribute

	def remove (self,attrid):
		self.pop(attrid)

	def watchdog (self):
		if Attribute.ID.INTERNAL_WATCHDOG in self:
			return self.pop(Attribute.ID.INTERNAL_WATCHDOG)
		return None

	def withdraw (self):
		if Attribute.ID.INTERNAL_WITHDRAW in self:
			self.pop(Attribute.ID.INTERNAL_WITHDRAW)
			return True
		return False

	def pack (self,negotiated,with_default=True):
		local_asn = negotiated.local_as
		peer_asn = negotiated.peer_as

		message = ''

		default = {
			Attribute.ID.ORIGIN:     lambda l,r: Origin(Origin.IGP),
			Attribute.ID.AS_PATH:    lambda l,r: ASPath([],[]) if l == r else ASPath([local_asn,],[]),
			Attribute.ID.LOCAL_PREF: lambda l,r: LocalPreference(100) if l == r else NOTHING,
		}

		check = {
			Attribute.ID.NEXT_HOP:   lambda l,r,nh: nh.ipv4() == True,
			Attribute.ID.LOCAL_PREF: lambda l,r,nh: l == r,
		}

		if with_default:
			keys = set(self.keys() + default.keys())
		else:
			keys = set(self.keys())

		for code in sorted(keys):
			if code in (Attribute.ID.INTERNAL_SPLIT, Attribute.ID.INTERNAL_WATCHDOG, Attribute.ID.INTERNAL_WITHDRAW, Attribute.ID.INTERNAL_NAME):
				continue
			if code in self:
				if code in check:
					if check[code](local_asn,peer_asn,self[code]):
						message += self[code].pack(negotiated)
						continue
				else:
					message += self[code].pack(negotiated)
					continue
			else:
				if code in default:
					message += default[code](local_asn,peer_asn).pack(negotiated)

		return message

	def json (self):
		if not self._json:
			self._json = ', '.join(self._generate_json())
		return self._json

	def __str__ (self):
		if not self._str:
			# XXX: FIXME: remove this ' ' + ? should it be done by the caller ?
			self._str = ''.join(self._generate_text())
		return self._str

	def index (self):
		# XXX: FIXME: something a little bit smaller memory wise ?
		if not self._idx:
			# idx = ''.join(self._generate_text(Attribute.ID.MED))
			idx = ''.join(self._generate_text())
			self._idx = '%s next-hop %s' % (idx, str(self[Attribute.ID.NEXT_HOP])) if Attribute.ID.NEXT_HOP in self else idx
		return self._idx

	@classmethod
	def unpack (cls,data,negotiated):
		try:
			if cls.cached:
				if data == cls.previous:
					return Attributes.cached
				elif cls.previous and data.startswith(cls.previous):
					attributes = Attributes()
					for key in Attributes.cached:
						attributes[key] = Attributes.cached[key]
					attributes.parse(data[len(cls.previous):],negotiated)
				else:
					attributes = cls().parse(data,negotiated)
			else:
				attributes = cls().parse(data,negotiated)

			if Attribute.ID.AS_PATH in attributes and Attribute.ID.AS4_PATH in attributes:
				attributes.merge_attributes()

			if Attribute.ID.MP_REACH_NLRI not in attributes and Attribute.ID.MP_UNREACH_NLRI not in attributes:
				cls.previous = data
				cls.cached = attributes
			else:
				cls.previous = ''
				cls.cache = None

			return attributes
		except IndexError:
			raise Notify(3,2,data)

	@staticmethod
	def flag_attribute_content (data):
		flag = Attribute.Flag(ord(data[0]))
		attr = Attribute.ID(ord(data[1]))

		if flag & Attribute.Flag.EXTENDED_LENGTH:
			length = unpack('!H',data[2:4])[0]
			return flag, attr, data[4:length+4]
		else:
			length = ord(data[2])
			return flag, attr , data[3:length+3]

	def parse (self,data,negotiated):
		if not data:
			return self

		# We do not care if the attribute are transitive or not as we do not redistribute
		flag = Attribute.Flag(ord(data[0]))
		aid = Attribute.ID(ord(data[1]))

		if flag & Attribute.Flag.EXTENDED_LENGTH:
			length = unpack('!H',data[2:4])[0]
			offset = 4
		else:
			length = ord(data[2])
			offset = 3

		data = data[offset:]
		next = data[length:]
		attribute = data[:length]

		logger = Logger()
		logger.parser(LazyFormat("parsing flag %x type %02x (%s) len %02x %s" % (flag,int(aid),aid,length,'payload ' if length else ''),od,data[:length]))

		# remove the PARTIAL bit before comparaison if the attribute is optional
		if aid in Attribute.attributes_optional:
			aid &= Attribute.Flag.MASK_PARTIAL & 0xFF
			# aid &= ~Attribute.Flag.PARTIAL & 0xFF  # cleaner than above (python use signed integer for ~)

		# handle the attribute if we know it
		if Attribute.registered(aid,flag):
			self.add(Attribute.unpack(aid,flag,attribute,negotiated))
			return self.parse(next,negotiated)
		# XXX: FIXME: we could use a fallback function here like capability

		# if we know the attribute but the flag is not what the RFC says. ignore it.
		if aid in Attribute.attributes_known:
			logger.parser('invalid flag for attribute %s (flag 0x%02X, aid 0x%02X)' % (Attribute.ID.names.get(aid,'unset'),flag,aid))
			return self.parse(next,negotiated)

		# it is an unknown transitive attribute we need to pass on
		if flag & Attribute.Flag.TRANSITIVE:
			logger.parser('unknown transitive attribute (flag 0x%02X, aid 0x%02X)' % (flag,aid))
			self.add(GenericAttribute(aid,flag|Attribute.Flag.PARTIAL,attribute),attribute)
			return self.parse(next,negotiated)

		# it is an unknown non-transitive attribute we can ignore.
		logger.parser('ignoring unknown non-transitive attribute (flag 0x%02X, aid 0x%02X)' % (flag,aid))
		return self.parse(next,negotiated)

	def merge_attributes (self):
		as2path = self[Attribute.ID.AS_PATH]
		as4path = self[Attribute.ID.AS4_PATH]
		self.remove(Attribute.ID.AS_PATH)
		self.remove(Attribute.ID.AS4_PATH)

		# this key is unique as index length is a two header, plus a number of ASN of size 2 or 4
		# so adding the : make the length odd and unique
		key = "%s:%s" % (as2path.index, as4path.index)

		# found a cache copy
		cached = Attribute.cache.get(Attribute.ID.AS_PATH,{}).get(key,None)
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


	def __hash__(self):
		# XXX: FIXME: not excellent... :-(
		return hash(repr(self))


	# Orange BAGPIPE code ..

	# test that sets of attributes exactly match
	# can't rely on __eq__ for this, because __eq__ relies on Attribute.__eq__ which does not look at attributes values

	def sameValuesAs(self,other):
		# we sort based on string representation since the items do not
		# necessarily implement __cmp__
		sorter = lambda x,y: cmp(repr(x), repr(y))

		try:
			for key in set(self.iterkeys()).union(set(other.iterkeys())):
				if key == Attribute.ID.MP_REACH_NLRI:
					continue

				sval = self[key]
				oval = other[key]

				# In the case where the attribute is, for instance, a list
				# we want to compare values independently of the order
				if isinstance(sval, collections.Iterable):
					if not isinstance(oval, collections.Iterable):
						return False

					sval = sorted(sval,sorter)
					oval = set(oval,sorter)

				if sval != oval:
					return False
			return True
		except KeyError:
				return False
