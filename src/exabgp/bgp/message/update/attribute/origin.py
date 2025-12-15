"""origin.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
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

    def __init__(self, packed: Buffer) -> None:
        """Initialize Origin from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_origin() for semantic construction.

        Args:
            packed: Raw attribute value bytes (single byte: 0=IGP, 1=EGP, 2=INCOMPLETE)
        """
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'Origin':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire

        Returns:
            Origin instance

        Raises:
            ValueError: If data is not exactly 1 byte or value is invalid
        """
        data = bytes(data)
        if len(data) != 1:
            raise ValueError(f'Origin requires exactly 1 byte, got {len(data)}')
        if data[0] > 2:
            raise ValueError(f'Invalid origin value: {data[0]}')
        return cls(data)

    @classmethod
    def from_int(cls, origin: int) -> 'Origin':
        """Create Origin from semantic value with validation.

        Args:
            origin: IGP (0), EGP (1), or INCOMPLETE (2)

        Returns:
            Origin instance

        Raises:
            ValueError: If origin value is invalid
        """
        if not 0 <= origin <= 2:
            raise ValueError(f'Invalid origin value: {origin}')
        return cls(bytes([origin]))

    @property
    def origin(self) -> int:
        """Get origin value by unpacking from bytes."""
        return self._packed[0]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Origin):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self.origin == other.origin

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def pack_attribute(self, negotiated: Negotiated | None = None) -> bytes:
        return self._attribute(self._packed)

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        if self.origin == Origin.IGP:
            return 'igp'
        if self.origin == Origin.EGP:
            return 'egp'
        if self.origin == Origin.INCOMPLETE:
            return 'incomplete'
        return 'invalid'

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Origin:
        # Wire data - use from_packet for validation
        return cls.from_packet(data)

    @classmethod
    def setCache(cls) -> None:
        # there can only be three, build them now
        IGP = Origin.from_int(Origin.IGP)
        EGP = Origin.from_int(Origin.EGP)
        INC = Origin.from_int(Origin.INCOMPLETE)

        cls.cache[Attribute.CODE.ORIGIN][IGP.pack_attribute()] = IGP
        cls.cache[Attribute.CODE.ORIGIN][EGP.pack_attribute()] = EGP
        cls.cache[Attribute.CODE.ORIGIN][INC.pack_attribute()] = INC


Origin.setCache()
