"""generic.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from typing import TYPE_CHECKING, ClassVar, Type

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from struct import pack

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.util import hexstring

# ============================================================= GenericAttribute
#

# Attribute length threshold for extended length encoding
MAX_SINGLE_OCTET_LENGTH: int = 0xFF  # Maximum value that fits in a single byte (255)


class GenericAttribute(Attribute):
    """Generic attribute for unknown/opaque attribute types.

    Stores packed wire-format bytes. Code and flag are stored as instance
    attributes since they're not class constants for generic attributes.
    """

    GENERIC: ClassVar[bool] = True

    def __init__(self, packed: Buffer, code: int, flag: int) -> None:
        """Initialize from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_generic() for semantic construction.

        Args:
            packed: Raw attribute payload bytes
            code: Attribute type code
            flag: Attribute flags
        """
        self._packed: bytes = packed
        self.ID: int = code
        self.FLAG: int = flag

    @classmethod
    def from_packet(cls, code: int, flag: int, data: Buffer) -> 'GenericAttribute':
        """Create from wire-format bytes.

        Args:
            code: Attribute type code
            flag: Attribute flags
            data: Raw attribute payload bytes

        Returns:
            GenericAttribute instance
        """
        return cls(bytes(data), code, flag)

    @classmethod
    def make_generic(cls, code: int, flag: int, data: Buffer) -> 'GenericAttribute':
        """Create from semantic values.

        Args:
            code: Attribute type code
            flag: Attribute flags
            data: Raw attribute payload bytes

        Returns:
            GenericAttribute instance
        """
        return cls(data, code, flag)

    @property
    def data(self) -> bytes:
        """Get the attribute payload data."""
        return self._packed

    @property
    def index(self) -> bytes:
        """Get the index (empty for generic attributes)."""
        return b''

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GenericAttribute):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        return '0x' + ''.join('{:02x}'.format(_) for _ in self._packed)

    def pack_attribute(self, negotiated: Negotiated | None = None) -> bytes:
        flag: int = self.FLAG
        length: int = len(self._packed)
        if length > MAX_SINGLE_OCTET_LENGTH:
            flag |= Attribute.Flag.EXTENDED_LENGTH
        len_value: bytes
        if flag & Attribute.Flag.EXTENDED_LENGTH:
            len_value = pack('!H', length)
        else:
            len_value = bytes([length])
        return bytes([flag, self.ID]) + len_value + self._packed

    @classmethod
    def unpack_attribute(cls: Type['GenericAttribute'], code: int, flag: int, data: Buffer) -> 'GenericAttribute':
        return cls.from_packet(code, flag, data)

    def json(self) -> str:
        return '{ "id": %d, "flag": %d, "payload": "%s"}' % (self.ID, self.FLAG, hexstring(self._packed))
