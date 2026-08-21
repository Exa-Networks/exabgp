"""community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json

from typing import TYPE_CHECKING, ClassVar, Type

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.util.types import Buffer

from struct import pack

# ======================================================= ExtendedCommunity (16)
#
# Subclasses register by (type, subtype) only - transitivity is a per-instance
# property determined from wire bits at runtime via transitive(), per RFC 4360.


class ExtendedCommunityBase(Attribute):
    """Base class for Extended Communities.

    Stores packed wire-format bytes. The first byte contains IANA and transitive bits,
    second byte is subtype, followed by value bytes.
    """

    COMMUNITY_TYPE: ClassVar[int] = 0x00  # MUST be redefined by subclasses
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x00  # MUST be redefined by subclasses
    NON_TRANSITIVE: ClassVar[int] = 0x40

    # Need to be overwritten by sub-classes
    registered_extended: ClassVar[dict[tuple[int, int], Type[ExtendedCommunityBase]] | None] = None

    @classmethod
    def register_subtype(cls, klass: Type[ExtendedCommunityBase]) -> Type[ExtendedCommunityBase]:
        """Register an extended community subclass by type/subtype.

        Note: Named differently from Attribute.register to avoid signature conflict.
        """
        assert cls.registered_extended is not None
        cls.registered_extended[(klass.COMMUNITY_TYPE & 0x0F, klass.COMMUNITY_SUBTYPE)] = klass
        return klass

    # size of value for data (boolean: is extended)
    length_value: ClassVar[dict[bool, int]] = {False: 7, True: 6}
    name: ClassVar[dict[bool, str]] = {False: 'regular', True: 'extended'}

    def __init__(self, packed: Buffer) -> None:
        """Initialize from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data.

        Args:
            packed: Raw extended community bytes
        """
        # Two top bits are iana and transitive bits
        self._packed: Buffer = packed
        self.registered_klass: Type[ExtendedCommunityBase] | None = None

    @classmethod
    def from_packet(cls, data: Buffer) -> 'ExtendedCommunityBase':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw extended community bytes from wire

        Returns:
            ExtendedCommunityBase instance (or appropriate subclass)
        """
        return cls(data)

    @property
    def community(self) -> Buffer:
        """Get the packed community bytes (for compatibility)."""
        return self._packed

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExtendedCommunityBase):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self._packed == other._packed

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ExtendedCommunityBase):
            raise TypeError(
                f"'<' not supported between instances of 'ExtendedCommunityBase' and '{type(other).__name__}'"
            )
        return bytes(self._packed) < bytes(other._packed)

    def __le__(self, other: object) -> bool:
        if not isinstance(other, ExtendedCommunityBase):
            raise TypeError(
                f"'<=' not supported between instances of 'ExtendedCommunityBase' and '{type(other).__name__}'"
            )
        return bytes(self._packed) <= bytes(other._packed)

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, ExtendedCommunityBase):
            raise TypeError(
                f"'>' not supported between instances of 'ExtendedCommunityBase' and '{type(other).__name__}'"
            )
        return bytes(self._packed) > bytes(other._packed)

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, ExtendedCommunityBase):
            raise TypeError(
                f"'>=' not supported between instances of 'ExtendedCommunityBase' and '{type(other).__name__}'"
            )
        return bytes(self._packed) >= bytes(other._packed)

    def iana(self) -> bool:
        return not not (self._packed[0] & 0x80)

    def transitive(self) -> bool:
        # bit set means "not transitive"
        # RFC4360:
        #   T - Transitive bit
        #     Value 0: The community is transitive across ASes
        #     Value 1: The community is non-transitive across ASes
        return not (self._packed[0] & 0x40)

    def pack_attribute(self, negotiated: Negotiated) -> Buffer:
        return self._packed

    def pack(self) -> Buffer:
        """Return packed bytes for sorting/comparison."""
        return self._packed

    def _subtype(self, transitive: bool = True) -> bytes:
        # if not transitive -> set the 'transitive' bit, as per RFC4360
        return pack(
            '!BB',
            self.COMMUNITY_TYPE if transitive else self.COMMUNITY_TYPE | self.NON_TRANSITIVE,
            self.COMMUNITY_SUBTYPE,
        )

    def _described(self) -> str:
        """How the registered class describes this community, or empty if it cannot.

        A registered class which does not define one inherits this class's, so delegating
        to it calls straight back here: TrafficRedirectASN4 and TrafficRedirectIPv6 both
        did, and eight bytes on the wire were enough to exhaust the stack inside the writer
        feeding the API subprocesses.  A RecursionError there is a dead process, not a
        dead session, and both are FlowSpec redirect communities: exactly what the
        controllers this API exists for receive.
        """
        klass = self.registered_klass
        if klass is None or klass.__repr__ is ExtendedCommunityBase.__repr__:
            return ''
        return klass.__repr__(self)

    def _value(self) -> int:
        h = 0x00
        for byte in self._packed:
            h <<= 8
            h += byte
        return h

    def json(self) -> str:
        return '{{ "value": {}, "string": {} }}'.format(self._value(), json.dumps(self._described()))

    def __repr__(self) -> str:
        return self._described() or '0x{:016X}'.format(self._value())

    def __hash__(self) -> int:
        return hash(self._packed)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> 'ExtendedCommunityBase':
        # 30/02/12 Quagga communities for soo and rt are not transitive when 4360 says they must be, hence the & 0x0FFF
        community = (data[0] & 0x0F, data[1])
        assert cls.registered_extended is not None
        if community in cls.registered_extended:
            klass = cls.registered_extended[community]
            instance = klass.unpack_attribute(data, negotiated)
            instance.registered_klass = klass
            return instance
        return cls.from_packet(data)


class ExtendedCommunity(ExtendedCommunityBase):
    """Extended Community attribute (code 16). 8 bytes."""

    ID = Attribute.CODE.EXTENDED_COMMUNITY
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

    registered_extended: ClassVar[dict[tuple[int, int], Type[ExtendedCommunityBase]]] = {}

    @classmethod
    def from_packet(cls, data: Buffer) -> 'ExtendedCommunity':
        """Validate and create from wire-format bytes."""
        if len(data) != 8:
            raise ValueError(f'ExtendedCommunity must be 8 bytes, got {len(data)}')
        return cls(data)

    def __len__(self) -> int:
        return 8


class ExtendedCommunityIPv6(ExtendedCommunityBase):
    """IPv6 Extended Community attribute (code 25). 20 bytes."""

    ID = Attribute.CODE.IPV6_EXTENDED_COMMUNITY
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

    registered_extended: ClassVar[dict[tuple[int, int], Type[ExtendedCommunityBase]]] = {}

    @classmethod
    def from_packet(cls, data: Buffer) -> 'ExtendedCommunityIPv6':
        """Validate and create from wire-format bytes."""
        if len(data) != 20:
            raise ValueError(f'ExtendedCommunityIPv6 must be 20 bytes, got {len(data)}')
        return cls(data)

    def __len__(self) -> int:
        return 20
