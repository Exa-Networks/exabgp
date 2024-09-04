# encoding: utf-8
"""
capability.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import sys

# Do not create a dependency loop by using exabgp.bgp.message as import
from exabgp.util import ordinal
from exabgp.util import concat_bytes_i

from exabgp.bgp.message.notification import Notify


class _CapabilityCode(int):
    _cache = dict()

    if sys.version_info[0] < 3:
        __slots__ = ['NAME', '_cache']

    RESERVED = 0x00  # [RFC5492]
    MULTIPROTOCOL = 0x01  # [RFC2858]
    ROUTE_REFRESH = 0x02  # [RFC2918]
    OUTBOUND_ROUTE_FILTERING = 0x03  # [RFC5291]
    MULTIPLE_ROUTES = 0x04  # [RFC3107]
    NEXTHOP = 0x05  # [RFC5549]
    EXTENDED_MESSAGE = 0x06  # https://tools.ietf.org/html/draft-ietf-idr-bgp-extended-messages-24

    # 6-63      Unassigned
    GRACEFUL_RESTART = 0x40  # [RFC4724]
    FOUR_BYTES_ASN = 0x41  # [RFC4893]
    # 66        Deprecated
    DYNAMIC_CAPABILITY = 0x43  # [Chen]
    MULTISESSION = 0x44  # [draft-ietf-idr-bgp-multisession]
    ADD_PATH = 0x45  # [draft-ietf-idr-add-paths]
    ENHANCED_ROUTE_REFRESH = 0x46  # [draft-ietf-idr-bgp-enhanced-route-refresh]
    # 70-127    Unassigned
    ROUTE_REFRESH_CISCO = 0x80  # I Can only find reference to this in the router logs
    # 128-255   Reserved for Private Use [RFC5492]
    MULTISESSION_CISCO = 0x83  # What Cisco really use for Multisession (yes this is a reserved range in prod !)

    HOSTNAME = 0xB8  # ExaBGP only ...
    OPERATIONAL = 0xB9  # ExaBGP only ...

    # Internal
    AIGP = 0xFF00

    names = {
        RESERVED: 'reserved',
        MULTIPROTOCOL: 'multiprotocol',
        ROUTE_REFRESH: 'route-refresh',
        OUTBOUND_ROUTE_FILTERING: 'outbound-route-filtering',
        MULTIPLE_ROUTES: 'multiple-routes',
        NEXTHOP: 'nexthop',
        EXTENDED_MESSAGE: 'extended-message',
        GRACEFUL_RESTART: 'graceful-restart',
        FOUR_BYTES_ASN: 'asn4',
        DYNAMIC_CAPABILITY: 'dynamic-capability',
        MULTISESSION: 'multi-session',
        ADD_PATH: 'add-path',
        ENHANCED_ROUTE_REFRESH: 'enhanced-route-refresh',
        OPERATIONAL: 'operational',
        ROUTE_REFRESH_CISCO: 'cisco-route-refresh',
        MULTISESSION_CISCO: 'cisco-multi-sesion',
        AIGP: 'aigp',
        HOSTNAME: 'exabgp-experimental-hostname',
        OPERATIONAL: 'exabgp-experimental-operational',
    }

    def __new__(cls, value):
        if value in cls._cache:
            return cls._cache[value]
        obj = super(_CapabilityCode, cls).__new__(cls, value)
        obj.NAME = cls.names.get(value, 'unknown capability %s' % hex(value))
        cls._cache[value] = obj
        return obj

    def __str__(self):
        return self.names.get(self, 'unknown capability %s' % hex(self))

    def __repr__(self):
        return str(self)

    def name(self):
        return self.names.get(self, 'unknown capability %s' % hex(self))


# =================================================================== Capability
#


class Capability(object):
    class CODE(int):
        if sys.version_info[0] < 3:
            __slots__ = []

        RESERVED = _CapabilityCode(_CapabilityCode.RESERVED)
        MULTIPROTOCOL = _CapabilityCode(_CapabilityCode.MULTIPROTOCOL)
        ROUTE_REFRESH = _CapabilityCode(_CapabilityCode.ROUTE_REFRESH)
        OUTBOUND_ROUTE_FILTERING = _CapabilityCode(_CapabilityCode.OUTBOUND_ROUTE_FILTERING)
        MULTIPLE_ROUTES = _CapabilityCode(_CapabilityCode.MULTIPLE_ROUTES)
        NEXTHOP = _CapabilityCode(_CapabilityCode.NEXTHOP)
        EXTENDED_MESSAGE = _CapabilityCode(_CapabilityCode.EXTENDED_MESSAGE)
        GRACEFUL_RESTART = _CapabilityCode(_CapabilityCode.GRACEFUL_RESTART)
        FOUR_BYTES_ASN = _CapabilityCode(_CapabilityCode.FOUR_BYTES_ASN)
        DYNAMIC_CAPABILITY = _CapabilityCode(_CapabilityCode.DYNAMIC_CAPABILITY)
        MULTISESSION = _CapabilityCode(_CapabilityCode.MULTISESSION)
        NEXTHOP = _CapabilityCode(_CapabilityCode.NEXTHOP)
        ADD_PATH = _CapabilityCode(_CapabilityCode.ADD_PATH)
        ENHANCED_ROUTE_REFRESH = _CapabilityCode(_CapabilityCode.ENHANCED_ROUTE_REFRESH)
        ROUTE_REFRESH_CISCO = _CapabilityCode(_CapabilityCode.ROUTE_REFRESH_CISCO)
        MULTISESSION_CISCO = _CapabilityCode(_CapabilityCode.MULTISESSION_CISCO)
        HOSTNAME = _CapabilityCode(_CapabilityCode.HOSTNAME)
        OPERATIONAL = _CapabilityCode(_CapabilityCode.OPERATIONAL)
        AIGP = _CapabilityCode(_CapabilityCode.AIGP)

        unassigned = range(70, 128)
        reserved = range(128, 256)

        def __str__(self):
            name = _CapabilityCode.names.get(self, None)
            if name is None:
                if self in Capability.CODE.unassigned:
                    return 'unassigned-%s' % hex(self)
                if self in Capability.CODE.reserved:
                    return 'reserved-%s' % hex(self)
                return 'capability-%s' % hex(self)
            return name

        def __repr__(self):
            return str(self)

        # XXX: Could use cls instead of _CapabilityCode and other tidy up
        @classmethod
        def name(cls, self):
            name = _CapabilityCode.names.get(self, None)
            if name is None:
                if self in Capability.CODE.unassigned:
                    return 'unassigned-%s' % hex(self)
                if self in Capability.CODE.reserved:
                    return 'reserved-%s' % hex(self)
            return name

    registered_capability = dict()
    unknown_capability = None

    @staticmethod
    def hex(data):
        return '0x' + ''.join('%02x' % ordinal(_) for _ in data)
        # return '0x' + concat_bytes_i('%02x' % ordinal(_) for _ in data)

    @classmethod
    def unknown(cls, klass):
        if cls.unknown_capability is not None:
            raise RuntimeError('only one fallback function can be registered')
        cls.unknown_capability = klass

    @classmethod
    def register(cls, capability=None):
        def register_capability(klass):
            # ID is defined by all the subclasses - otherwise they do not work :)
            what = klass.ID if capability is None else capability  # pylint: disable=E1101
            if what in cls.registered_capability:
                raise RuntimeError('only one class can be registered per capability')
            cls.registered_capability[what] = klass
            return klass

        return register_capability

    @classmethod
    def klass(cls, what):
        if what in cls.registered_capability:
            kls = cls.registered_capability[what]
            kls.ID = what
            return kls
        if cls.unknown_capability:
            return cls.unknown_capability
        raise Notify(2, 4, 'can not handle capability %s' % what)

    @classmethod
    def unpack(cls, capability, capabilities, data):
        instance = capabilities.get(capability, Capability.klass(capability)())
        return cls.klass(capability).unpack_capability(instance, data, capability)
