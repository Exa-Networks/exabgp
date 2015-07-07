# encoding: utf-8
"""
attribute.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack

from exabgp.bgp.message.notification import Notify

from exabgp.util.cache import Cache


# ==================================================================== Attribute
#

class Attribute (object):
	# we need to define ID and FLAG inside of the subclasses
	ID   = 0x00
	FLAG = 0x00

	# Should this Attribute be cached
	CACHING = False
	# Generic Class or implementation
	GENERIC = False

	# Registered subclasses we know how to decode
	registered_attributes = dict()

	# what this implementation knows as attributes
	attributes_known = []
	attributes_well_know = []
	attributes_optional = []

	# Are we caching Attributes (configuration)
	caching = False

	# The attribute cache per attribute ID
	cache = {}

	# ---------------------------------------------------------------------------

	# XXX: FIXME: The API of ID is a bit different (it can be instanciated)
	# XXX: FIXME: This is legacy. should we change to not be ?
	class CODE (int):
		__slots__ = []

		# This should move within the classes and not be here
		# RFC 4271
		ORIGIN             = 0x01
		AS_PATH            = 0x02
		NEXT_HOP           = 0x03
		MED                = 0x04
		LOCAL_PREF         = 0x05
		ATOMIC_AGGREGATE   = 0x06
		AGGREGATOR         = 0x07
		# RFC 1997
		COMMUNITY          = 0x08
		# RFC 4456
		ORIGINATOR_ID      = 0x09
		CLUSTER_LIST       = 0x0A  # 10
		# RFC 4760
		MP_REACH_NLRI      = 0x0E  # 14
		MP_UNREACH_NLRI    = 0x0F  # 15
		# RFC 4360
		EXTENDED_COMMUNITY = 0x10  # 16
		# RFC 4893
		AS4_PATH           = 0x11  # 17
		AS4_AGGREGATOR     = 0x12  # 18
		# RFC6514
		PMSI_TUNNEL        = 0x16  # 22
		# RFC5512
		TUNNEL_ENCAP       = 0x17  # 23
		AIGP               = 0x1A  # 26

		INTERNAL_NAME      = 0xFFFC
		INTERNAL_WITHDRAW  = 0xFFFD
		INTERNAL_WATCHDOG  = 0xFFFE
		INTERNAL_SPLIT     = 0xFFFF

		names = {
			ORIGIN:             'origin',
			AS_PATH:            'as-path',
			NEXT_HOP:           'next-hop',
			MED:                'med',              # multi-exit-disc
			LOCAL_PREF:         'local-preference',
			ATOMIC_AGGREGATE:   'atomic-aggregate',
			AGGREGATOR:         'aggregator',
			COMMUNITY:          'community',
			ORIGINATOR_ID:      'originator-id',
			CLUSTER_LIST:       'cluster-list',
			MP_REACH_NLRI:      'mp-reach-nlri',    # multi-protocol reacheable nlri
			MP_UNREACH_NLRI:    'mp-unreach-nlri',  # multi-protocol unreacheable nlri
			EXTENDED_COMMUNITY: 'extended-community',
			AS4_PATH:           'as4-path',
			AS4_AGGREGATOR:     'as4-aggregator',
			PMSI_TUNNEL:        'pmsi-tunnel',
			TUNNEL_ENCAP:       'tunnel-encaps',
			AIGP:               'aigp',
			0xfffc:             'internal-name',
			0xfffd:             'internal-withdraw',
			0xfffe:             'internal-watchdog',
			0xffff:             'internal-split',
		}

		def __repr__ (self):
			return self.names.get(self,'unknown-attribute-%s' % hex(self))

		def __str__ (self):
			return repr(self)

		@classmethod
		def name (cls, self):
			return cls.names.get(self,'unknown-attribute-%s' % hex(self))

	# ---------------------------------------------------------------------------

	class Flag (int):
		EXTENDED_LENGTH = 0x10  # .  16 - 0001 0000
		PARTIAL         = 0x20  # .  32 - 0010 0000
		TRANSITIVE      = 0x40  # .  64 - 0100 0000
		OPTIONAL        = 0x80  # . 128 - 1000 0000

		MASK_EXTENDED   = 0xEF  # . 239 - 1110 1111
		MASK_PARTIAL    = 0xDF  # . 223 - 1101 1111
		MASK_TRANSITIVE = 0xBF  # . 191 - 1011 1111
		MASK_OPTIONAL   = 0x7F  # . 127 - 0111 1111

		__slots__ = []

		def __str__ (self):
			r = []
			v = int(self)
			if v & 0x10:
				r.append("EXTENDED_LENGTH")
				v -= 0x10
			if v & 0x20:
				r.append("PARTIAL")
				v -= 0x20
			if v & 0x40:
				r.append("TRANSITIVE")
				v -= 0x40
			if v & 0x80:
				r.append("OPTIONAL")
				v -= 0x80
			if v:
				r.append("UNKNOWN %s" % hex(v))
			return " ".join(r)

		def matches (self, value):
			return self | 0x10 == value | 0x10

	# ---------------------------------------------------------------------------

	def _attribute (self, value):
		flag = self.FLAG
		if flag & Attribute.Flag.OPTIONAL and not value:
			return ''
		length = len(value)
		if length > 0xFF:
			flag |= Attribute.Flag.EXTENDED_LENGTH
		if flag & Attribute.Flag.EXTENDED_LENGTH:
			len_value = pack('!H',length)
		else:
			len_value = chr(length)
		return "%s%s%s%s" % (chr(flag),chr(self.ID),len_value,value)

	def _len (self,value):
		length = len(value)
		return length + 3 if length <= 0xFF else length + 4

	def __eq__ (self, other):
		return \
			self.ID == other.ID and \
			self.FLAG == other.FLAG

	def __ne__ (self, other):
		return not self.__eq__(other)

	def __lt__ (self, other):
		return self.ID < other.ID

	def __le__ (self, other):
		return self.ID <= other.ID

	def __gt__ (self, other):
		return self.ID > other.ID

	def __ge__ (self, other):
		return self.ID >= other.ID

	@classmethod
	def register (cls,attribute_id=None,flag=None):
		def register_attribute (klass):
			aid = klass.ID if attribute_id is None else attribute_id
			flg = klass.FLAG | Attribute.Flag.EXTENDED_LENGTH if flag is None else flag | Attribute.Flag.EXTENDED_LENGTH
			if (aid,flg) in cls.registered_attributes:
				raise RuntimeError('only one class can be registered per attribute')
			cls.registered_attributes[(aid,flg)] = klass
			cls.attributes_known.append(aid)
			if klass.FLAG & Attribute.Flag.OPTIONAL:
				cls.attributes_optional.append(aid)
			else:
				cls.attributes_well_know.append(aid)
			return klass
		return register_attribute

	@classmethod
	def registered (cls, attribute_id, flag):
		return (attribute_id,flag | Attribute.Flag.EXTENDED_LENGTH) in cls.registered_attributes

	@classmethod
	def klass (cls, attribute_id, flag):
		key = (attribute_id,flag | Attribute.Flag.EXTENDED_LENGTH)
		if key in cls.registered_attributes:
			kls = cls.registered_attributes[key]
			kls.ID = attribute_id
			return kls
		# XXX: we do see some AS4_PATH with the partial instead of transitive bit set !!
		if attribute_id == Attribute.CODE.AS4_PATH:
			kls = cls.attributes_known[attribute_id]
			kls.ID = attribute_id
			return kls
		raise Notify (2,4,'can not handle attribute id %s' % attribute_id)

	@classmethod
	def unpack (cls, attribute_id, flag, data, negotiated):
		cache = cls.caching and cls.CACHING

		if cache and data in cls.cache.get(cls.ID,{}):
			return cls.cache[cls.ID].retrieve(data)

		key = (attribute_id,flag | Attribute.Flag.EXTENDED_LENGTH)
		if key in Attribute.registered_attributes.keys():
			instance = cls.klass(attribute_id,flag).unpack(data,negotiated)

			if cache:
				cls.cache[cls.ID].cache(data,instance)
			return instance

		raise Notify (2,4,'can not handle attribute id %s' % attribute_id)

	@classmethod
	def setCache (cls):
		if not cls.cache:
			for attribute in Attribute.CODE.names:
				if attribute not in cls.cache:
					cls.cache[attribute] = Cache()

Attribute.setCache()
