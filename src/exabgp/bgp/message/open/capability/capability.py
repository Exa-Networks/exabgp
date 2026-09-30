"""capability.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Do not create a dependency loop by using exabgp.bgp.message as import

from __future__ import annotations

from typing import (
    Any,
    Callable,
    ClassVar,
    Generic,
    ItemsView,
    Iterable,
    Iterator,
    KeysView,
    Type,
    TypeVar,
    ValuesView,
    overload,
)

from exabgp.bgp.message.notification import Notify
from exabgp.util.intvalue import IntValue
from exabgp.util.types import Buffer


def decode_utf8(data: Buffer, what: str) -> str:
    """Decode a peer supplied string from a capability.

    The peer controls these bytes, so a decoding failure must end the session with
    a NOTIFICATION and not with a UnicodeDecodeError escaping the parser.

    Args:
        data: The raw bytes to decode
        what: Name of the field, used in the error message

    Returns:
        The decoded string

    Raises:
        Notify: If the bytes are not valid UTF-8
    """
    try:
        return bytes(data).decode('utf-8')
    except UnicodeDecodeError as exc:
        raise Notify(2, 0, f'the {what} in the capability is not valid UTF-8 ({exc})') from None


class CapabilityCode(IntValue):
    RESERVED: ClassVar[int] = 0x00  # [RFC5492]
    MULTIPROTOCOL: ClassVar[int] = 0x01  # [RFC2858]
    ROUTE_REFRESH: ClassVar[int] = 0x02  # [RFC2918]
    OUTBOUND_ROUTE_FILTERING: ClassVar[int] = 0x03  # [RFC5291]
    MULTIPLE_ROUTES: ClassVar[int] = 0x04  # [RFC3107]
    NEXTHOP: ClassVar[int] = 0x05  # [RFC5549]
    EXTENDED_MESSAGE: ClassVar[int] = 0x06  # https://tools.ietf.org/html/draft-ietf-idr-bgp-extended-messages-24
    MULTIPLE_LABELS: ClassVar[int] = 0x08  # [RFC8277]
    ROLE: ClassVar[int] = 0x09  # [RFC9234]

    # 6-63      Unassigned
    GRACEFUL_RESTART: ClassVar[int] = 0x40  # [RFC4724]
    FOUR_BYTES_ASN: ClassVar[int] = 0x41  # [RFC4893]
    # 66        Deprecated
    DYNAMIC_CAPABILITY: ClassVar[int] = 0x43  # [Chen]
    MULTISESSION: ClassVar[int] = 0x44  # [draft-ietf-idr-bgp-multisession]
    ADD_PATH: ClassVar[int] = 0x45  # [draft-ietf-idr-add-paths]
    ENHANCED_ROUTE_REFRESH: ClassVar[int] = 0x46  # [draft-ietf-idr-bgp-enhanced-route-refresh]
    PATHS_LIMIT: ClassVar[int] = 0x4C  # [draft-abraitis-idr-addpath-paths-limit]
    LINK_LOCAL_NEXTHOP: ClassVar[int] = 0x4D  # [draft-ietf-idr-linklocal-capability]
    # 78-127    Unassigned
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
        ROLE: 'role',
        GRACEFUL_RESTART: 'graceful-restart',
        FOUR_BYTES_ASN: 'asn4',
        DYNAMIC_CAPABILITY: 'dynamic-capability',
        MULTISESSION: 'multi-session',
        ADD_PATH: 'add-path',
        ENHANCED_ROUTE_REFRESH: 'enhanced-route-refresh',
        PATHS_LIMIT: 'paths-limit',
        MULTIPLE_LABELS: 'multiple-labels',
        LINK_LOCAL_NEXTHOP: 'link-local-nexthop',
        OPERATIONAL: 'operational',
        ROUTE_REFRESH_CISCO: 'cisco-route-refresh',
        MULTISESSION_CISCO: 'cisco-multi-sesion',
        AIGP: 'aigp',
        HOSTNAME: 'hostname',
        SOFTWARE_VERSION: 'software-version',
    }

    NAME: str

    def __init__(self, value: int) -> None:
        super().__init__(value)
        self.NAME = self.name()

    def __str__(self) -> str:
        return self.name()

    def __repr__(self) -> str:
        return str(self)

    def name(self) -> str:
        return self.names.get(self.value, 'unknown capability {}'.format(hex(self.value)))


# =================================================================== Capability
#


class CapabilityCodes:
    # fmt: off
    RESERVED: ClassVar[CapabilityCode] =                 CapabilityCode(CapabilityCode.RESERVED)
    MULTIPROTOCOL: ClassVar[CapabilityCode] =            CapabilityCode(CapabilityCode.MULTIPROTOCOL)
    ROUTE_REFRESH: ClassVar[CapabilityCode] =            CapabilityCode(CapabilityCode.ROUTE_REFRESH)
    OUTBOUND_ROUTE_FILTERING: ClassVar[CapabilityCode] = CapabilityCode(CapabilityCode.OUTBOUND_ROUTE_FILTERING)
    MULTIPLE_ROUTES: ClassVar[CapabilityCode] =          CapabilityCode(CapabilityCode.MULTIPLE_ROUTES)
    NEXTHOP: ClassVar[CapabilityCode] =                  CapabilityCode(CapabilityCode.NEXTHOP)
    EXTENDED_MESSAGE: ClassVar[CapabilityCode] =         CapabilityCode(CapabilityCode.EXTENDED_MESSAGE)
    ROLE: ClassVar[CapabilityCode] =                     CapabilityCode(CapabilityCode.ROLE)
    GRACEFUL_RESTART: ClassVar[CapabilityCode] =         CapabilityCode(CapabilityCode.GRACEFUL_RESTART)
    FOUR_BYTES_ASN: ClassVar[CapabilityCode] =           CapabilityCode(CapabilityCode.FOUR_BYTES_ASN)
    DYNAMIC_CAPABILITY: ClassVar[CapabilityCode] =       CapabilityCode(CapabilityCode.DYNAMIC_CAPABILITY)
    MULTISESSION: ClassVar[CapabilityCode] =             CapabilityCode(CapabilityCode.MULTISESSION)
    ADD_PATH: ClassVar[CapabilityCode] =                 CapabilityCode(CapabilityCode.ADD_PATH)
    ENHANCED_ROUTE_REFRESH: ClassVar[CapabilityCode] =   CapabilityCode(CapabilityCode.ENHANCED_ROUTE_REFRESH)
    PATHS_LIMIT: ClassVar[CapabilityCode] =              CapabilityCode(CapabilityCode.PATHS_LIMIT)
    MULTIPLE_LABELS: ClassVar[CapabilityCode] =          CapabilityCode(CapabilityCode.MULTIPLE_LABELS)
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

    @classmethod
    def name(cls, self: int) -> str | None:
        name: str | None = CapabilityCode.names.get(self, None)
        if name is None:
            if self in Capability.CODE.unassigned:
                return 'unassigned-{}'.format(hex(self))
            if self in Capability.CODE.reserved:
                return 'reserved-{}'.format(hex(self))
        return name


class Capability:
    CODE: ClassVar[type[CapabilityCodes]] = CapabilityCodes

    registered_capability: ClassVar[dict[CapabilityCode, Type[Capability]]] = dict()
    unknown_capability: ClassVar[Type[Capability] | None] = None

    # The code the class is registered under. RouteRefresh and MultiSession are also
    # registered under a Cisco code: an instance says which one it is with code().
    ID: ClassVar[CapabilityCode]
    # The wire code of this instance when it is not ID, set by unpack() or by whoever
    # builds the Cisco variant. mypyc cannot let an instance shadow a class attribute.
    wire_code: CapabilityCode | None = None

    def code(self) -> CapabilityCode:
        """The code this capability is sent, or was received, under."""
        return self.wire_code if self.wire_code is not None else self.ID

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
    def register(cls, capability: CapabilityCode | None = None) -> Callable[[Type[Capability]], Type[Capability]]:
        def register_capability(klass: Type[Capability]) -> Type[Capability]:
            # ID is defined by all the subclasses - otherwise they do not work :)
            what: CapabilityCode = klass.ID if capability is None else capability  # pylint: disable=E1101
            if what in cls.registered_capability:
                raise RuntimeError('only one class can be registered per capability')
            cls.registered_capability[what] = klass
            return klass

        return register_capability

    @classmethod
    def klass(cls, what: CapabilityCode) -> Type[Capability]:
        if what in cls.registered_capability:
            return cls.registered_capability[what]
        if cls.unknown_capability:
            return cls.unknown_capability
        # RFC 5492 3 forbids a NOTIFICATION for a capability we do not support, and
        # UnknownCapability is registered by importing this package, so reaching here
        # means our registry is broken, not that the peer did anything wrong
        raise RuntimeError(f'no class and no fallback registered for capability {what}')

    @classmethod
    def unpack(cls, capability: CapabilityCode, capabilities: Any, data: Buffer) -> Capability:
        instance: Capability = capabilities.get(capability, Capability.klass(capability)())
        # Record the wire code actually received on this instance (not the shared class):
        # some capabilities (RouteRefresh, MultiSession) are registered under both an RFC
        # and a Cisco code, and klass() resolves the same class object for either. Keeping
        # it on the instance means one peer's variant never leaks into another
        # already-unpacked instance's str()/json() output.
        instance.wire_code = capability
        return cls.klass(capability).unpack_capability(instance, data, capability)


_Item = TypeVar('_Item')


class CapabilityList(Capability, Generic[_Item]):
    """A capability whose value is a list of entries: families, codes, next hop conversions.

    These inherited from both Capability and list, which mypyc cannot compile. The entries
    live in `.items` and this gives back what the code used of the list: iteration, length,
    membership, indexing, append and extend, false when empty, and equality with a list of
    the same entries.
    """

    def __init__(self, items: Iterable[_Item] = ()) -> None:
        self.items: list[_Item] = list(items)

    def __iter__(self) -> Iterator[_Item]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    def __contains__(self, item: object) -> bool:
        return item in self.items

    def __getitem__(self, index: int) -> _Item:
        return self.items[index]

    def append(self, item: _Item) -> None:
        self.items.append(item)

    def extend(self, items: Iterable[_Item]) -> None:
        self.items.extend(items)

    # defining __eq__ leaves the class unhashable, as the list was
    def __eq__(self, other: object) -> bool:
        if isinstance(other, CapabilityList):
            return self.items == other.items
        if isinstance(other, list):
            return self.items == other
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        # the operator, not a call to __eq__: it answers NotImplemented the way Python does,
        # where a compiled bool-typed local would refuse it
        return not self == other


_Key = TypeVar('_Key')
_Value = TypeVar('_Value')


class CapabilityDict(Capability, Generic[_Key, _Value]):
    """A capability whose value maps a family to something: ADD-PATH, graceful restart, ...

    These inherited from both Capability and dict, which mypyc cannot compile. The mapping
    lives in `.entries` and this gives back what the code used of the dict: indexing and
    assignment, membership, iteration over the keys, get, items, keys and values, length,
    false when empty, and equality with a dict of the same entries.
    """

    def __init__(self) -> None:
        self.entries: dict[_Key, _Value] = {}

    def __getitem__(self, key: _Key) -> _Value:
        return self.entries[key]

    def __setitem__(self, key: _Key, value: _Value) -> None:
        self.entries[key] = value

    def __contains__(self, key: object) -> bool:
        return key in self.entries

    def __iter__(self) -> Iterator[_Key]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def __bool__(self) -> bool:
        return bool(self.entries)

    @overload
    def get(self, key: _Key) -> _Value | None: ...

    @overload
    def get(self, key: _Key, default: _Value) -> _Value: ...

    def get(self, key: _Key, default: _Value | None = None) -> _Value | None:
        return self.entries.get(key, default)

    def clear(self) -> None:
        self.entries.clear()

    def items(self) -> ItemsView[_Key, _Value]:
        return self.entries.items()

    def keys(self) -> KeysView[_Key]:
        return self.entries.keys()

    def values(self) -> ValuesView[_Value]:
        return self.entries.values()

    # defining __eq__ leaves the class unhashable, as the dict was
    def __eq__(self, other: object) -> bool:
        if isinstance(other, CapabilityDict):
            return self.entries == other.entries
        if isinstance(other, dict):
            return self.entries == other
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        # the operator, not a call to __eq__: it answers NotImplemented the way Python does,
        # where a compiled bool-typed local would refuse it
        return not self == other
