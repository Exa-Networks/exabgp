# encoding: utf-8
"""
attribute.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import pack

from exabgp.bgp.message.update.attribute.flag import Flag

from exabgp.bgp.message.notification import Notify

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
	registered_attributes = dict()
	registered_codes = dict()

	# Are we caching Attributes (configuration)
	caching = False

	# The attribute cache per attribute ID
	cache = {}

	# XXX : FIXME : The API of ID is a bit different (it can be instanciated)
	# XXX : FIXME : This is legacy. should we change to not be ?
	class ID (int):
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

		INTERNAL_WITHDRAW  = 0xFFFD
		INTERNAL_WATCHDOG  = 0xFFFE
		INTERNAL_SPLIT     = 0xFFFF

		names = {
			0x01: 'origin',
			0x02: 'as-path',
			0x03: 'next-hop',
			0x04: 'med',
	#		0x04: 'multi-exit-disc',
			0x05: 'local-preference',
			0x06: 'atomic-aggregate',
			0x07: 'aggregator',
			0x08: 'community',
			0x09: 'originator-id',
			0x0a: 'cluster-list',
			0x0e: 'mp-reach-nlri',
			0x0f: 'mp-unreach-nlri',
	#		0x0e: 'multi-protocol reacheable nlri'
	#		0x0f: 'multi-protocol unreacheable nlri'
			0x10: 'extended-community',
			0x11: 'as4-path',
			0x12: 'as4-aggregator',
			0x16: 'pmsi-tunnel',
			0x17: 'tunnel-encaps',
			0x1a: 'aigp',
			0xfffd: 'internal-withdraw',
			0xfffe: 'internal-watchdog',
			0xffff: 'internal-split',
		}

		def __str__ (self):
			return self.names.get(self,'unknown-attribute-%s' % hex(self))

		@classmethod
		def name (cls,self):
			return cls.names.get(self,'unknown-attribute-%s' % hex(self))


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
	def register_attribute (cls,attribute_id=None,flag=None):
		aid = cls.ID if attribute_id is None else attribute_id
		flg = cls.FLAG | Flag.EXTENDED_LENGTH if flag is None else flag | Flag.EXTENDED_LENGTH
		if (aid,flg) in cls.registered_attributes:
			raise RuntimeError('only one class can be registered per capability')
		cls.registered_attributes[(aid,flg)] = cls
		cls.registered_codes[aid] = cls

	@classmethod
	def registered (cls,attribute_id,flag):
		return (attribute_id,flag | Flag.EXTENDED_LENGTH) in cls.registered_attributes

	@classmethod
	def klass (cls,attribute_id,flag):
		key = (attribute_id,flag | Flag.EXTENDED_LENGTH)
		if key in cls.registered_attributes:
			kls = cls.registered_attributes[key]
			kls.ID = attribute_id
			return kls
		raise Notify (2,4,'can not handle attribute id %s' % attribute_id)

	@classmethod
	def unpack (cls,attribute_id,flag,data,negotiated):
		cache = cls.caching and cls.CACHING

		if cache and data in cls.cache.get(cls.ID,{}):
			return cls.cache[cls.ID].retrieve(data)

		key = (attribute_id,flag | Flag.EXTENDED_LENGTH)
		if key in Attribute.registered_attributes.keys():
			instance = cls.klass(attribute_id,flag).unpack(data,negotiated)

			if cache:
				cls.cache.cache[cls.ID].cache(data,instance)
			return instance

		raise Notify (2,4,'can not handle attribute id %s' % attribute_id)

	@classmethod
	def setCache (cls):
		if not cls.cache:
			for attribute in Attribute.ID.names:
				if attribute not in cls.cache:
					cls.cache[attribute] = Cache()

Attribute.setCache()
