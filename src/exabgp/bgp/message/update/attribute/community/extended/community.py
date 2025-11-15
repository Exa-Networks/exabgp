"""community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Dict, Optional, Tuple, Type

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute import Attribute

from struct import pack

# ======================================================= ExtendedCommunity (16)
# XXX: Should subclasses register with transitivity ?


class ExtendedCommunityBase(Attribute):
    COMMUNITY_TYPE: ClassVar[int] = 0x00  # MUST be redefined by subclasses
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x00  # MUST be redefined by subclasses
    NON_TRANSITIVE: ClassVar[int] = 0x40

    # Need to be overwritten by sub-classes
    registered_extended: ClassVar[Optional[Dict[Tuple[int, int], Type[ExtendedCommunityBase]]]] = None

    @classmethod
    def register(cls, klass: Type[ExtendedCommunityBase]) -> Type[ExtendedCommunityBase]:
        cls.registered_extended[(klass.COMMUNITY_TYPE & 0x0F, klass.COMMUNITY_SUBTYPE)] = klass  # type: ignore[index]
        return klass

    # size of value for data (boolean: is extended)
    length_value: ClassVar[Dict[bool, int]] = {False: 7, True: 6}
    name: ClassVar[Dict[bool, str]] = {False: 'regular', True: 'extended'}

    def __init__(self, community: bytes) -> None:
        # Two top bits are iana and transitive bits
        self.community: bytes = community
        self.klass: Optional[Type[ExtendedCommunityBase]] = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExtendedCommunityBase):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self.community == other.community

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ExtendedCommunityBase):
            return NotImplemented
        return self.community < other.community

    def __le__(self, other: object) -> bool:
        if not isinstance(other, ExtendedCommunityBase):
            return NotImplemented
        return self.community <= other.community

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, ExtendedCommunityBase):
            return NotImplemented
        return self.community > other.community

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, ExtendedCommunityBase):
            return NotImplemented
        return self.community >= other.community

    def iana(self) -> bool:
        return not not (self.community[0] & 0x80)

    def transitive(self) -> bool:
        # bit set means "not transitive"
        # RFC4360:
        #   T - Transitive bit
        #     Value 0: The community is transitive across ASes
        #     Value 1: The community is non-transitive across ASes
        return not (self.community[0] & 0x40)

    def pack(self, negotiated: Negotiated = None) -> bytes:  # type: ignore[assignment]
        return self.community

    def _subtype(self, transitive: bool = True) -> bytes:
        # if not transitive -> set the 'transitive' bit, as per RFC4360
        return pack(
            '!BB',
            self.COMMUNITY_TYPE if transitive else self.COMMUNITY_TYPE | self.NON_TRANSITIVE,
            self.COMMUNITY_SUBTYPE,
        )

    def json(self) -> str:
        h = 0x00
        for byte in self.community:
            h <<= 8
            h += byte
        s = self.klass.__repr__(self) if self.klass else ''
        return '{{ "value": {}, "string": "{}" }}'.format(h, s)

    def __repr__(self) -> str:
        if self.klass:
            return self.klass.__repr__(self)
        h = 0x00
        for byte in self.community:
            h <<= 8
            h += byte
        return '0x{:016X}'.format(h)

    def __hash__(self) -> int:
        return hash(self.community)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Optional[Negotiated] = None) -> ExtendedCommunityBase:
        # 30/02/12 Quagga communities for soo and rt are not transitive when 4360 says they must be, hence the & 0x0FFF
        community = (data[0] & 0x0F, data[1])
        if community in cls.registered_extended:  # type: ignore[operator]
            klass = cls.registered_extended[community]  # type: ignore[index]
            instance = klass.unpack_attribute(data, negotiated)
            instance.klass = klass
            return instance
        return cls(data)


class ExtendedCommunity(ExtendedCommunityBase):
    ID = Attribute.CODE.EXTENDED_COMMUNITY
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

    registered_extended: ClassVar[Dict[Tuple[int, int], Type[ExtendedCommunityBase]]] = {}

    def __len__(self) -> int:
        return 8


class ExtendedCommunityIPv6(ExtendedCommunityBase):
    ID = Attribute.CODE.IPV6_EXTENDED_COMMUNITY
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

    registered_extended: ClassVar[Dict[Tuple[int, int], Type[ExtendedCommunityBase]]] = {}

    def __len__(self) -> int:
        return 20
