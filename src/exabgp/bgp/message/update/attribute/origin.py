"""origin.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute.attribute import Attribute


# =================================================================== Origin (1)


@Attribute.register()
class Origin(Attribute):
    ID = Attribute.CODE.ORIGIN
    FLAG = Attribute.Flag.TRANSITIVE
    CACHING = True
    TREAT_AS_WITHDRAW = True
    MANDATORY = True

    IGP: ClassVar[int] = 0x00
    EGP: ClassVar[int] = 0x01
    INCOMPLETE: ClassVar[int] = 0x02

    def __init__(self, packed: bytes) -> None:
        """Initialize Origin from packed wire-format bytes.

        Args:
            packed: Raw attribute value bytes (single byte: 0=IGP, 1=EGP, 2=INCOMPLETE)
        """
        self._packed: bytes = packed

    @classmethod
    def make_origin(cls, origin: int) -> 'Origin':
        """Create Origin from semantic value.

        Args:
            origin: IGP (0), EGP (1), or INCOMPLETE (2)

        Returns:
            Origin instance
        """
        return cls(bytes([origin]))

    @property
    def origin(self) -> int:
        """Get origin value by unpacking from bytes."""
        if not self._packed:
            raise IndexError('Origin has no data (truncated or malformed)')
        return self._packed[0]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Origin):
            return False
        if not self._packed or not other._packed:
            return self._packed == other._packed
        return self.ID == other.ID and self.FLAG == other.FLAG and self.origin == other.origin

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def pack_attribute(self, negotiated: Negotiated | None = None) -> bytes:
        return self._attribute(self._packed)

    def __len__(self) -> int:
        # Origin is always 1 byte payload + 3 byte header = 4 bytes total
        return 4

    def __repr__(self) -> str:
        if not self._packed:
            return 'invalid'
        if self.origin == Origin.IGP:
            return 'igp'
        if self.origin == Origin.EGP:
            return 'egp'
        if self.origin == Origin.INCOMPLETE:
            return 'incomplete'
        return 'invalid'

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> Origin:
        if len(data) != 1:
            from exabgp.bgp.message.notification import Notify

            raise Notify(3, 5, f'Origin attribute has invalid length {len(data)}, expected 1')
        return cls(data)

    @classmethod
    def setCache(cls) -> None:
        # there can only be three, build them now
        IGP = Origin.make_origin(Origin.IGP)
        EGP = Origin.make_origin(Origin.EGP)
        INC = Origin.make_origin(Origin.INCOMPLETE)

        cls.cache[Attribute.CODE.ORIGIN][IGP.pack_attribute()] = IGP
        cls.cache[Attribute.CODE.ORIGIN][EGP.pack_attribute()] = EGP
        cls.cache[Attribute.CODE.ORIGIN][INC.pack_attribute()] = INC


Origin.setCache()
