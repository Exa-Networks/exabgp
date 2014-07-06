# encoding: utf-8
"""
attribute/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import pack

from exabgp.bgp.message.update.attribute.flag import Flag
from exabgp.bgp.message.update.attribute.id import AttributeID as AID

from exabgp.util.cache import Cache


# ==================================================================== Attribute
#

class Attribute (object):
	# we need to define ID and FLAG inside of the subclasses
	# otherwise we can not dynamically create different UnknownAttribute
	# ID   = 0x00
	# FLAG = 0x00

	# Should this Attribute be cached
	CACHING = False

	# Registered subclasses we know how to decode
	attributes = dict()

	# Are we caching Attributes (configuration)
	caching = False

	# The attribute cache per attribute ID
	cache = {}

	def _attribute (self,value):
		flag = self.FLAG
		if flag & Flag.OPTIONAL and not value:
			return ''
		length = len(value)
		if length > 0xFF:
			flag |= Flag.EXTENDED_LENGTH
		if flag & Flag.EXTENDED_LENGTH:
			len_value = pack('!H',length)
		else:
			len_value = chr(length)
		return "%s%s%s%s" % (chr(flag),chr(self.ID),len_value,value)

	def __eq__ (self,other):
		return self.ID == other.ID

	def __ne__ (self,other):
		return self.ID != other.ID

	@classmethod
	def register (cls,attribute_id=None,flag=None):
		aid = cls.ID if attribute_id is None else attribute_id
		flg = cls.FLAG | 0x10 if flag is None else flag | 0x10
		if (aid,flg) in cls.attributes:
			raise RuntimeError('only one class can be registered per capability')
		cls.attributes[(aid,flg)] = cls

	@classmethod
	def registered (cls,attribute_id,flag):
		return (attribute_id,flag | 0x10) in cls.attributes

	@classmethod
	def klass (cls,attribute_id,flag):
		key = (attribute_id,flag | 0x10)
		if key in cls.attributes:
			kls = cls.attributes[key]
			kls.ID = attribute_id
			return kls
		raise Notify (2,4,'can not handle attribute id %s' % attribute_id)

	@classmethod
	def unpack (cls,attribute_id,flag,data,negotiated):
		cache = cls.caching and cls.CACHING

		if cache and data in cls.cache.get(cls.ID,{}):
			return cls.cache[cls.ID].retrieve(data)

		key = (attribute_id,flag | 0x10)
		if key in Attribute.attributes.keys():
			instance = cls.klass(attribute_id,flag).unpack(data,negotiated)

			if cache:
				cls.cache.cache[cls.ID].cache(data,instance)
			return instance

		return UnknownAttribute(attribute_id,flag,data)

	@classmethod
	def setCache (cls):
		if not cls.cache:
			for attribute in AID._str:  # XXX: better way to find the keys ?
				if attribute not in cls.cache:
					cls.cache[attribute] = Cache()

Attribute.setCache()


import collections
from struct import unpack

from exabgp.util.od import od
from exabgp.configuration.environment import environment

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.attribute.aspath import ASPath  # ,AS4Path
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
# from exabgp.bgp.message.update.attribute.med import MED
# from exabgp.bgp.message.update.attribute.aggregator import Aggregator
# from exabgp.bgp.message.update.attribute.community import Communities,ExtendedCommunities
# from exabgp.bgp.message.update.attribute.originatorid import OriginatorID
# from exabgp.bgp.message.update.attribute.clusterlist import ClusterList
# from exabgp.bgp.message.update.attribute.pmsi import PMSI
#from exabgp.bgp.message.update.attribute.pmsi import PMSI
# from exabgp.bgp.message.update.attribute.aigp import AIGP

# from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
# from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI

from exabgp.bgp.message.update.attribute.unknown import UnknownAttribute

from exabgp.logger import Logger,LazyFormat

class _NOTHING (object):
	def pack (self,asn4=None):
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

	def pack (self,asn4=None):
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

# lookup = {
# 	AID.ORIGIN             : Origin,               # 1
# 	AID.AS_PATH            : ASPath,               # 2
# 	# NextHop                                      # 3
# 	AID.MED                : MED,                  # 4
# 	AID.LOCAL_PREF         : LocalPreference,      # 5
# 	AID.ATOMIC_AGGREGATE   : AtomicAggregate,      # 6
# 	AID.AGGREGATOR         : Aggregator,           # 7
# 	AID.COMMUNITY          : Communities,          # 8
# 	AID.ORIGINATOR_ID      : OriginatorID,         # 9
# 	AID.CLUSTER_LIST       : ClusterList,          # 10
# 	AID.EXTENDED_COMMUNITY : ExtendedCommunities,  # 16
# 	AID.AS4_PATH           : AS4Path,              # 17
# 	AID.AS4_AGGREGATOR     : Aggregator,           # 18
# 	AID.PMSI_TUNNEL        : PMSI,                 # 22
# 	AID.AIGP               : AIGP,                 # 26
# }

class Attributes (dict):
	# A cache of parsed attributes
	cache = {}

	# The previously parsed Attributes
	cached = None
	# previously parsed attribute, from which cached was made of
	previous = ''

	representation = {
		#	key:  (how, default, name, presentation),
		AID.ORIGIN             : ('string',  '', 'origin', '%s'),
		AID.AS_PATH            : ('multiple','', ('as-path','as-set'), '%s'),
		AID.NEXT_HOP           : ('string',  '', 'next-hop', '%s'),
		AID.MED                : ('integer', '', 'med', '%s'),
		AID.LOCAL_PREF         : ('integer', '', 'local-preference', '%s'),
		AID.ATOMIC_AGGREGATE   : ('boolean', '', 'atomic-aggregate', '%s'),
		AID.AGGREGATOR         : ('string',  '', 'aggregator', '( %s )'),
		AID.AS4_AGGREGATOR     : ('string',  '', 'aggregator', '( %s )'),
		AID.COMMUNITY          : ('list',    '', 'community', '%s'),
		AID.ORIGINATOR_ID      : ('inet',    '', 'originator-id', '%s'),
		AID.CLUSTER_LIST       : ('list',    '', 'cluster-list', '%s'),
		AID.EXTENDED_COMMUNITY : ('list',    '', 'extended-community', '%s'),
		AID.PMSI_TUNNEL        : ('string',  '', 'pmsi', '%s'),
		AID.AIGP               : ('integer', '', 'aigp', '%s'),
	}

	def __init__ (self):
		# cached representation of the object
		self._str = ''
		self._idx = ''
		self._json = ''
		# The parsed attributes have no mp routes and/or those are last
		self.cacheable = True

		# XXX: FIXME: we should cache the attributes parsed, should it be set elsewhere ?
		Attribute.cache = environment.settings().cache.attributes

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
				raise Notify(3,0,'multiple attribute for %s' % str(AID(attribute.ID)))
			self[attribute.ID] = attribute

	def remove (self,attrid):
		self.pop(attrid)

	def watchdog (self):
		if AID.INTERNAL_WATCHDOG in self:
			return self.pop(AID.INTERNAL_WATCHDOG)
		return None

	def withdraw (self):
		if AID.INTERNAL_WITHDRAW in self:
			self.pop(AID.INTERNAL_WITHDRAW)
			return True
		return False

	def pack (self,negotiated,with_default=True):
		asn4 = negotiated.asn4
		local_asn = negotiated.local_as
		peer_asn = negotiated.peer_as

		if negotiated.neighbor.aigp is None:
			aigp = True if local_asn == peer_asn else False
		else:
			aigp = negotiated.neighbor.aigp

		message = ''

		default = {
			AID.ORIGIN:     lambda l,r: Origin(Origin.IGP),
			AID.AS_PATH:    lambda l,r: ASPath([],[]) if l == r else ASPath([local_asn,],[]),
			AID.LOCAL_PREF: lambda l,r: LocalPreference(100) if l == r else NOTHING,
		}

		check = {
			AID.NEXT_HOP:   lambda l,r,nh: nh.ipv4() == True,
			AID.LOCAL_PREF: lambda l,r,nh: l == r,
		}

		if with_default:
			keys = set(self.keys() + default.keys())
		else:
			keys = set(self.keys())

		# AGGREGATOR generate both AGGREGATOR and AS4_AGGREGATOR
		for code in sorted(keys):
			if code in (AID.INTERNAL_SPLIT, AID.INTERNAL_WATCHDOG, AID.INTERNAL_WITHDRAW):
				continue
			if code in self:
				if code == AID.AIGP and not aigp:
					continue
				if code in check:
					if check[code](local_asn,peer_asn,self[code]):
						message += self[code].pack(asn4)
						continue
				else:
					message += self[code].pack(asn4)
					continue
			else:
				if code in default:
					message += default[code](local_asn,peer_asn).pack(asn4)

		return message

	def json (self):
		if not self._json:
			def generate (self):
				for code in sorted(self.keys() + [AID.ATOMIC_AGGREGATE,]):
					# remove the next-hop from the attribute as it is define with the NLRI
					if code in (AID.NEXT_HOP, AID.INTERNAL_SPLIT, AID.INTERNAL_WATCHDOG, AID.INTERNAL_WITHDRAW):
						continue
					if code in self.representation:
						how, default, name, presentation = self.representation[code]
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
			self._json = ', '.join(generate(self))
		return self._json

	def __str__ (self):
		if not self._str:
			def generate (self):
				for code in sorted(self.keys()):
					# XXX: FIXME: really we should have a INTERNAL attribute in the classes
					if code in (AID.INTERNAL_SPLIT, AID.INTERNAL_WATCHDOG, AID.INTERNAL_WITHDRAW, AID.NEXT_HOP):
						continue
					if code in self.representation:
						how, default, name, presentation = self.representation[code]
						if how == 'boolean':
							yield ' %s' % name
						elif how == 'multiple':
							yield ' %s %s' % (name[0], presentation % str(self[code]))
						else:
							yield ' %s %s' % (name, presentation % str(self[code]))
					else:
						yield ' attribute [ 0x%02X 0x%02X %s ]' % (code,self[code].FLAG,str(self[code]))
			# XXX: FIXME: remove this ' ' + ? should it be done by the caller ?
			self._str = ''.join(generate(self))
		return self._str

	def index (self):
		# XXX: FIXME: something a little bit smaller memory wise ?
		if not self._idx:
			self._idx = '%s next-hop %s' % (str(self), str(self[AID.NEXT_HOP])) if AID.NEXT_HOP in self else str(self)
		return self._idx

	@classmethod
	def unpack (cls,data,negotiated):
		try:
			if cls.cached:
				if data == cls.previous:
					return Attributes.cached
				elif data.startswith(cls.previous):
					attributes = Attributes()
					for key in Attributes.cached:
						attributes[key] = Attributes.cached[key]
					attributes.parse(data[len(cls.previous):],negotiated)
				else:
					attributes = cls().parse(data,negotiated)
			else:
				attributes = cls().parse(data,negotiated)

			if AID.AS_PATH in attributes and AID.AS4_PATH in attributes:
				attributes.merge_attributes()

			if AID.MP_REACH_NLRI not in attributes and AID.MP_UNREACH_NLRI not in attributes:
				cls.previous = data
				cls.cached = attributes
			else:
				cls.previous = ''
				cls.cache = None

			return attributes
		except IndexError:
			raise Notify(3,2,data)

	def parse (self,data,negotiated):
		if not data:
			return self

		# We do not care if the attribute are transitive or not as we do not redistribute
		flag = Flag(ord(data[0]))
		code = AID(ord(data[1]))

		if flag & Flag.EXTENDED_LENGTH:
			length = unpack('!H',data[2:4])[0]
			offset = 4
		else:
			length = ord(data[2])
			offset = 3

		data = data[offset:]
		next = data[length:]
		attribute = data[:length]

		logger = Logger()
		logger.parser(LazyFormat("parsing flag %x type %02x (%s) len %02x %s" % (flag,int(code),code,length,'payload ' if length else ''),od,data[:length]))

		if Attribute.registered(code,flag):
			self.add(Attribute.unpack(code,flag,attribute,negotiated))
			return self.parse(next,negotiated)
		elif flag & Flag.TRANSITIVE:
			self.add(UnknownAttribute(code,flag,attribute),attribute)
			logger.parser('unknown transitive attribute (code 0x%02X, flag 0x%02X)' % (code,flag))
			return self.parse(next,negotiated)
		else:
			logger.parser('ignoring non-transitive attribute (code 0x%02X, flag 0x%02X)' % (code,flag))
			return self.parse(next,negotiated)


	def merge_attributes (self):
		as2path = self[AID.AS_PATH]
		as4path = self[AID.AS4_PATH]
		self.remove(AID.AS_PATH)
		self.remove(AID.AS4_PATH)

		# this key is unique as index length is a two header, plus a number of ASN of size 2 or 4
		# so adding the : make the length odd and unique
		key = "%s:%s" % (as2path.index, as4path.index)

		# found a cache copy
		if self.add_from_cache(AID.AS_PATH,key):
			return

		as_seq = []
		as_set = []

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

	# test that sets of attributes exactly match
	# can't rely on __eq__ for this, because __eq__ relies on Attribute.__eq__ which does not look at attributes values

	def sameValuesAs(self,other):
		# we sort based on string representation since the items do not
		# necessarily implement __cmp__
		sorter = lambda x,y: cmp(repr(x), repr(y))

		try:
			for key in set(self.iterkeys()).union(set(other.iterkeys())):
				if key == AID.MP_REACH_NLRI:
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
