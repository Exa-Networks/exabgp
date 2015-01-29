# encoding: utf-8
"""
capability.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.notification import Notify


# =================================================================== Capability
#

class Capability (object):

	class CODE (int):
		__slots__ = []

		RESERVED                 = 0x00  # [RFC5492]
		MULTIPROTOCOL            = 0x01  # [RFC2858]
		ROUTE_REFRESH            = 0x02  # [RFC2918]
		OUTBOUND_ROUTE_FILTERING = 0x03  # [RFC5291]
		MULTIPLE_ROUTES          = 0x04  # [RFC3107]
		EXTENDED_NEXT_HOP        = 0x05  # [RFC5549]
		# 6-63      Unassigned
		GRACEFUL_RESTART         = 0x40  # [RFC4724]
		FOUR_BYTES_ASN           = 0x41  # [RFC4893]
		# 66        Deprecated
		DYNAMIC_CAPABILITY       = 0x43  # [Chen]
		MULTISESSION             = 0x44  # [draft-ietf-idr-bgp-multisession]
		ADD_PATH                 = 0x45  # [draft-ietf-idr-add-paths]
		ENHANCED_ROUTE_REFRESH   = 0x46  # [draft-ietf-idr-bgp-enhanced-route-refresh]
		OPERATIONAL              = 0x47  # ExaBGP only ...
		# 70-127    Unassigned
		ROUTE_REFRESH_CISCO      = 0x80  # I Can only find reference to this in the router logs
		# 128-255   Reserved for Private Use [RFC5492]
		MULTISESSION_CISCO       = 0x83  # What Cisco really use for Multisession (yes this is a reserved range in prod !)

		EXTENDED_MESSAGE         = -1    # No yet defined by draft http://tools.ietf.org/html/draft-ietf-idr-extended-messages-02.txt

		unassigned = range(70,128)
		reserved = range(128,256)

		# Internal
		AIGP = 0xFF00

		names = {
			RESERVED:                  'reserved',
			MULTIPROTOCOL:             'multiprotocol',
			ROUTE_REFRESH:             'route-refresh',
			OUTBOUND_ROUTE_FILTERING:  'outbound-route-filtering',
			MULTIPLE_ROUTES:           'multiple-routes',
			EXTENDED_NEXT_HOP:         'extended-next-hop',

			GRACEFUL_RESTART:          'graceful-restart',
			FOUR_BYTES_ASN:            'asn4',

			DYNAMIC_CAPABILITY:        'dynamic-capability',
			MULTISESSION:              'multi-session',
			ADD_PATH:                  'add-path',
			ENHANCED_ROUTE_REFRESH:    'enhanced-route-refresh',
			OPERATIONAL:               'operational',

			ROUTE_REFRESH_CISCO:       'cisco-route-refresh',
			MULTISESSION_CISCO:        'cisco-multi-sesion',

			AIGP:                      'aigp',
		}

		def __str__ (self):
			name = self.names.get(self,None)
			if name is None:
				if self in Capability.CODE.unassigned:
					return 'unassigned-%s' % hex(self)
				if self in Capability.CODE.reserved:
					return 'reserved-%s' % hex(self)
				return 'capability-%s' % hex(self)
			return name

		def __repr__ (self):
			return str(self)

		@classmethod
		def name (cls, self):
			name = cls.names.get(self,None)
			if name is None:
				if self in Capability.CODE.unassigned:
					return 'unassigned-%s' % hex(self)
				if self in Capability.CODE.reserved:
					return 'reserved-%s' % hex(self)
			return name

	registered_capability = dict()
	_fallback_capability = None

	@staticmethod
	def hex (data):
		return '0x' + ''.join('%02x' % ord(_) for _ in data)

	@classmethod
	def fallback_capability (cls, imp):
		if cls._fallback_capability is not None:
			raise RuntimeError('only one fallback function can be registered')
		cls._fallback_capability = imp

	@staticmethod
	def register_capability (klass, capability=None):
		# ID is defined by all the subclasses - otherwise they do not work :)
		what = klass.ID if capability is None else capability  # pylint: disable=E1101
		if what in klass.registered_capability:
			raise RuntimeError('only one class can be registered per capability')
		klass.registered_capability[what] = klass

	@classmethod
	def klass (cls, what):
		if what in cls.registered_capability:
			kls = cls.registered_capability[what]
			kls.ID = what
			return kls
		if cls._fallback_capability:
			return cls._fallback_capability
		raise Notify (2,4,'can not handle capability %s' % what)

	@classmethod
	def unpack (cls, capability, capabilities, data):
		instance = capabilities.get(capability,Capability.klass(capability)())
		return cls.klass(capability).unpack_capability(instance,data,capability)
