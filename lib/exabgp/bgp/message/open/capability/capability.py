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
	_known = dict()
	_fallback = None

	@staticmethod
	def hex (data):
		return '0x' + ''.join('%02x' % ord(_) for _ in data)

	@classmethod
	def fallback (cls):
		if cls._fallback is not None:
			raise RuntimeError('only one fallback function can be registered')
		cls._fallback = cls

	@classmethod
	def register (cls,capability=None):
		what = cls.ID if capability is None else capability
		if what in cls._known:
			raise RuntimeError('only one class can be registered per capability')
		cls._known[what] = cls

	@classmethod
	def klass (cls,what):
		if what in cls._known:
			kls = cls._known[what]
			kls.ID = what
			return kls
		if cls._fallback:
			return cls._fallback
		raise Notify (2,4,'can not handle capability %s' % what)

	@classmethod
	def unpack (cls,capability,capabilities,data):
			if capability in capabilities:
				return cls.klass(capability).unpack(capability,capabilities[capability],data)
			return cls.klass(capability).unpack(capability,Capability.klass(capability)(),data)
