"""originatorid.py

Created by Thomas Mangin on 2012-07-07.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.protocol.ip import IP, IPv4

# ============================================================== OriginatorID (9)


@Attribute.register()
class OriginatorID(Attribute):
    """Originator ID attribute (code 9).

    Stores packed wire-format bytes (4 bytes IPv4 address).
    Delegates IP functionality via composition rather than inheritance.
    """

    ID: int = Attribute.CODE.ORIGINATOR_ID
    FLAG: int = Attribute.Flag.OPTIONAL
    CACHING: ClassVar[bool] = True

    def __init__(self, packed: Buffer) -> None:
        """Initialize from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_originatorid() for semantic construction.

        Args:
            packed: Raw IPv4 address bytes (4 bytes)
        """
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'OriginatorID':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire

        Returns:
            OriginatorID instance

        Raises:
            ValueError: If data length is not 4
        """
        if len(data) != 4:
            raise ValueError(f'OriginatorID must be 4 bytes, got {len(data)}')
        return cls(data)

    @classmethod
    def from_string(cls, ip_string: str) -> 'OriginatorID':
        """Create from IP address string.

        Args:
            ip_string: IPv4 address as string (e.g., '192.168.1.1')

        Returns:
            OriginatorID instance
        """
        packed = IPv4.pton(ip_string)
        return cls(packed)

    def top(self, negotiated: Negotiated | None = None) -> str:
        """Get string representation of the IP address."""
        return IP.ntop(self._packed)

    def ton(self, negotiated: Negotiated | None = None) -> Buffer:
        """Get packed bytes representation."""
        return self._packed

    def pack_ip(self) -> Buffer:
        """Get packed bytes (IP interface compatibility)."""
        return self._packed

    def index(self) -> Buffer:
        """Get the packed data for indexing/caching."""
        return self._packed

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OriginatorID):
            return False
        return self.ID == other.ID and self.FLAG == other.FLAG and self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        return self.top()

    def __hash__(self) -> int:
        return hash(('OriginatorID', self._packed))

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        return self._attribute(self._packed)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
        return cls.from_packet(data)
