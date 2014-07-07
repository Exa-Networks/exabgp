# encoding: utf-8
"""
capability.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.notification import Notify


# =================================================================== Capability
#

class Capability (object):
	registered_capability = dict()
	_fallback_capability = None

	@staticmethod
	def hex (data):
		return '0x' + ''.join('%02x' % ord(_) for _ in data)

	@classmethod
	def fallback_capability (cls):
		if cls._fallback_capability is not None:
			raise RuntimeError('only one fallback function can be registered')
		cls._fallback_capability = cls

	@classmethod
	def register_capability (cls,capability=None):
		what = cls.ID if capability is None else capability
		if what in cls.registered_capability:
			raise RuntimeError('only one class can be registered per capability')
		cls.registered_capability[what] = cls

	@classmethod
	def klass (cls,what):
		if what in cls.registered_capability:
			kls = cls.registered_capability[what]
			kls.ID = what
			return kls
		if cls._fallback_capability:
			return cls._fallback_capability
		raise Notify (2,4,'can not handle capability %s' % what)

	@classmethod
	def unpack (cls,capability,capabilities,data):
		if capability in capabilities:
			return cls.klass(capability).unpack(capability,capabilities[capability],data)
		return cls.klass(capability).unpack(capability,Capability.klass(capability)(),data)
