"""capability.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Do not create a dependency loop by using exabgp.bgp.message as import

from __future__ import annotations

from typing import Any, Callable, ClassVar, Type

from exabgp.bgp.message.notification import Notify
from exabgp.util.types import Buffer


class CapabilityCode(int):
    _cache: ClassVar[dict[int, CapabilityCode]] = dict()

    RESERVED: ClassVar[int] = 0x00  # [RFC5492]
    MULTIPROTOCOL: ClassVar[int] = 0x01  # [RFC2858]
    ROUTE_REFRESH: ClassVar[int] = 0x02  # [RFC2918]
    OUTBOUND_ROUTE_FILTERING: ClassVar[int] = 0x03  # [RFC5291]
    MULTIPLE_ROUTES: ClassVar[int] = 0x04  # [RFC3107]
    NEXTHOP: ClassVar[int] = 0x05  # [RFC5549]
    EXTENDED_MESSAGE: ClassVar[int] = 0x06  # https://tools.ietf.org/html/draft-ietf-idr-bgp-extended-messages-24

    # 6-63      Unassigned
    GRACEFUL_RESTART: ClassVar[int] = 0x40  # [RFC4724]
    FOUR_BYTES_ASN: ClassVar[int] = 0x41  # [RFC4893]
    # 66        Deprecated
    DYNAMIC_CAPABILITY: ClassVar[int] = 0x43  # [Chen]
    MULTISESSION: ClassVar[int] = 0x44  # [draft-ietf-idr-bgp-multisession]
    ADD_PATH: ClassVar[int] = 0x45  # [draft-ietf-idr-add-paths]
    ENHANCED_ROUTE_REFRESH: ClassVar[int] = 0x46  # [draft-ietf-idr-bgp-enhanced-route-refresh]
    LINK_LOCAL_NEXTHOP: ClassVar[int] = 0x4D  # [draft-ietf-idr-linklocal-capability]
    # 70-127    Unassigned
    ROUTE_REFRESH_CISCO: ClassVar[int] = 0x80  # I Can only find reference to this in the router logs
    # 128-255   Reserved for Private Use [RFC5492]
    MULTISESSION_CISCO: ClassVar[int] = (
        0x83  # What Cisco really use for Multisession (yes this is a reserved range in prod !)
    )

    HOSTNAME: ClassVar[int] = 0x49  # https://datatracker.ietf.org/doc/html/draft-walton-bgp-hostname-capability-02
    SOFTWARE_VERSION: ClassVar[int] = (
        0x4B  # https://datatracker.ietf.org/doc/html/draft-abraitis-bgp-version-capability
    )
    OPERATIONAL: ClassVar[int] = 0xB9  # ExaBGP only ...

    # Internal
    AIGP: ClassVar[int] = 0xFF00

    names: ClassVar[dict[int, str]] = {
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
        LINK_LOCAL_NEXTHOP: 'link-local-nexthop',
        OPERATIONAL: 'operational',
        ROUTE_REFRESH_CISCO: 'cisco-route-refresh',
        MULTISESSION_CISCO: 'cisco-multi-sesion',
        AIGP: 'aigp',
        HOSTNAME: 'hostname',
        SOFTWARE_VERSION: 'software-version',
    }

    NAME: str

    def __new__(cls, value: int) -> CapabilityCode:
        if value in cls._cache:
            return cls._cache[value]
        obj: CapabilityCode = super(CapabilityCode, cls).__new__(cls, value)
        obj.NAME = cls.names.get(value, 'unknown capability {}'.format(hex(value)))
        cls._cache[value] = obj
        return obj

    def __str__(self) -> str:
        return self.names.get(self, 'unknown capability {}'.format(hex(self)))

    def __repr__(self) -> str:
        return str(self)

    def name(self) -> str:
        return self.names.get(self, 'unknown capability {}'.format(hex(self)))


# =================================================================== Capability
#


class Capability:
    class CODE(int):
        # fmt: off
        RESERVED: ClassVar[CapabilityCode] =                 CapabilityCode(CapabilityCode.RESERVED)
        MULTIPROTOCOL: ClassVar[CapabilityCode] =            CapabilityCode(CapabilityCode.MULTIPROTOCOL)
        ROUTE_REFRESH: ClassVar[CapabilityCode] =            CapabilityCode(CapabilityCode.ROUTE_REFRESH)
        OUTBOUND_ROUTE_FILTERING: ClassVar[CapabilityCode] = CapabilityCode(CapabilityCode.OUTBOUND_ROUTE_FILTERING)
        MULTIPLE_ROUTES: ClassVar[CapabilityCode] =          CapabilityCode(CapabilityCode.MULTIPLE_ROUTES)
        NEXTHOP: ClassVar[CapabilityCode] =                  CapabilityCode(CapabilityCode.NEXTHOP)
        EXTENDED_MESSAGE: ClassVar[CapabilityCode] =         CapabilityCode(CapabilityCode.EXTENDED_MESSAGE)
        GRACEFUL_RESTART: ClassVar[CapabilityCode] =         CapabilityCode(CapabilityCode.GRACEFUL_RESTART)
        FOUR_BYTES_ASN: ClassVar[CapabilityCode] =           CapabilityCode(CapabilityCode.FOUR_BYTES_ASN)
        DYNAMIC_CAPABILITY: ClassVar[CapabilityCode] =       CapabilityCode(CapabilityCode.DYNAMIC_CAPABILITY)
        MULTISESSION: ClassVar[CapabilityCode] =             CapabilityCode(CapabilityCode.MULTISESSION)
        ADD_PATH: ClassVar[CapabilityCode] =                 CapabilityCode(CapabilityCode.ADD_PATH)
        ENHANCED_ROUTE_REFRESH: ClassVar[CapabilityCode] =   CapabilityCode(CapabilityCode.ENHANCED_ROUTE_REFRESH)
        LINK_LOCAL_NEXTHOP: ClassVar[CapabilityCode] =       CapabilityCode(CapabilityCode.LINK_LOCAL_NEXTHOP)
        ROUTE_REFRESH_CISCO: ClassVar[CapabilityCode] =      CapabilityCode(CapabilityCode.ROUTE_REFRESH_CISCO)
        MULTISESSION_CISCO: ClassVar[CapabilityCode] =       CapabilityCode(CapabilityCode.MULTISESSION_CISCO)
        HOSTNAME: ClassVar[CapabilityCode] =                 CapabilityCode(CapabilityCode.HOSTNAME)
        SOFTWARE_VERSION: ClassVar[CapabilityCode] =         CapabilityCode(CapabilityCode.SOFTWARE_VERSION)
        OPERATIONAL: ClassVar[CapabilityCode] =              CapabilityCode(CapabilityCode.OPERATIONAL)
        AIGP: ClassVar[CapabilityCode] =                     CapabilityCode(CapabilityCode.AIGP)
        # fmt: on

        unassigned: ClassVar[range] = range(70, 128)
        reserved: ClassVar[range] = range(128, 256)

        def __str__(self) -> str:
            name: str | None = CapabilityCode.names.get(self, None)
            if name is None:
                if self in Capability.CODE.unassigned:
                    return 'unassigned-{}'.format(hex(self))
                if self in Capability.CODE.reserved:
                    return 'reserved-{}'.format(hex(self))
                return 'capability-{}'.format(hex(self))
            return name

        def __repr__(self) -> str:
            return str(self)

        @classmethod
        def name(cls, self: int) -> str | None:
            name: str | None = CapabilityCode.names.get(self, None)
            if name is None:
                if self in Capability.CODE.unassigned:
                    return 'unassigned-{}'.format(hex(self))
                if self in Capability.CODE.reserved:
                    return 'reserved-{}'.format(hex(self))
            return name

    registered_capability: ClassVar[dict[int, Type[Capability]]] = dict()
    unknown_capability: ClassVar[Type[Capability] | None] = None

    # ID attribute set by subclasses
    ID: ClassVar[int]

    def extract_capability_bytes(self) -> list[bytes]:
        """Extract capability data for encoding. Subclasses must implement."""
        raise NotImplementedError(f'{type(self).__name__}.extract_capability_bytes() not implemented')

    @classmethod
    def unpack_capability(cls, instance: 'Capability', data: Buffer, capability: CapabilityCode) -> 'Capability':
        """Unpack capability from bytes. Subclasses must implement."""
        raise NotImplementedError(f'{cls.__name__}.unpack_capability() not implemented')

    @staticmethod
    def hex(data: Buffer) -> str:
        return '0x' + ''.join('{:02x}'.format(_) for _ in data)

    @classmethod
    def unknown(cls, klass: Type[Capability]) -> Type[Capability]:
        if cls.unknown_capability is not None:
            raise RuntimeError('only one fallback function can be registered')
        cls.unknown_capability = klass
        return klass

    @classmethod
    def register(cls, capability: int | None = None) -> Callable[[Type[Capability]], Type[Capability]]:
        def register_capability(klass: Type[Capability]) -> Type[Capability]:
            # ID is defined by all the subclasses - otherwise they do not work :)
            what: int = klass.ID if capability is None else capability  # pylint: disable=E1101
            if what in cls.registered_capability:
                raise RuntimeError('only one class can be registered per capability')
            cls.registered_capability[what] = klass
            return klass

        return register_capability

    @classmethod
    def klass(cls, what: int) -> Type[Capability]:
        if what in cls.registered_capability:
            kls: Type[Capability] = cls.registered_capability[what]
            kls.ID = what
            return kls
        if cls.unknown_capability:
            return cls.unknown_capability
        raise Notify(2, 4, 'can not handle capability {}'.format(what))

    @classmethod
    def unpack(cls, capability: CapabilityCode, capabilities: Any, data: Buffer) -> Capability:
        instance: Capability = capabilities.get(capability, Capability.klass(capability)())
        return cls.klass(capability).unpack_capability(instance, data, capability)
