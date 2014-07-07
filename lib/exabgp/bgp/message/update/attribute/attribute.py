# encoding: utf-8
"""
attribute.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import pack

from exabgp.bgp.message.update.attribute.flag import Flag
from exabgp.bgp.message.update.attribute.id import AttributeID as AID

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
	def register_attribute (cls,attribute_id=None,flag=None):
		aid = cls.ID if attribute_id is None else attribute_id
		flg = cls.FLAG | 0x10 if flag is None else flag | 0x10
		if (aid,flg) in cls.registered_attributes:
			raise RuntimeError('only one class can be registered per capability')
		cls.registered_attributes[(aid,flg)] = cls

	@classmethod
	def registered (cls,attribute_id,flag):
		return (attribute_id,flag | 0x10) in cls.registered_attributes

	@classmethod
	def klass (cls,attribute_id,flag):
		key = (attribute_id,flag | 0x10)
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

		key = (attribute_id,flag | 0x10)
		if key in Attribute.registered_attributes.keys():
			instance = cls.klass(attribute_id,flag).unpack(data,negotiated)

			if cache:
				cls.cache.cache[cls.ID].cache(data,instance)
			return instance

		raise Notify (2,4,'can not handle attribute id %s' % attribute_id)

	@classmethod
	def setCache (cls):
		if not cls.cache:
			for attribute in AID._str:  # XXX: better way to find the keys ?
				if attribute not in cls.cache:
					cls.cache[attribute] = Cache()

Attribute.setCache()
