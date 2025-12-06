"""aigp.py

Created by Thomas Mangin on 2013-09-24.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from struct import pack, unpack
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute.attribute import Attribute

# ========================================================================== TLV
#

# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |     Type      |         Length                |               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+               |
# ~                                                               ~
# |                           Value                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+..........................

# Length: Two octets encoding the length in octets of the TLV,
# including the type and length fields.


# ==================================================================== AIGP (26)
#
# AIGP TLV format:
#   Type (1 byte): 1 = IGP metric
#   Length (2 bytes): Total TLV length including header (11 for IGP metric)
#   Value (8 bytes): uint64 metric value


@Attribute.register()
class AIGP(Attribute):
    ID = Attribute.CODE.AIGP
    FLAG = Attribute.Flag.OPTIONAL
    CACHING = True
    TYPES: ClassVar[list[int]] = [1]

    # TLV header for IGP metric: type=1, length=11 (3 header + 8 value)
    _TLV_HEADER: ClassVar[bytes] = b'\x01\x00\x0b'
    _TLV_LENGTH: ClassVar[int] = 11

    def __init__(self, packed: Buffer) -> None:
        """Initialize AIGP from packed TLV bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_aigp() for semantic construction.

        Args:
            packed: Raw TLV bytes (11 bytes: 1 type + 2 length + 8 value)
        """
        self._packed: Buffer = packed

    @classmethod
    def from_packet(cls, data: Buffer) -> 'AIGP':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw TLV bytes from wire

        Returns:
            AIGP instance

        Raises:
            ValueError: If data is malformed
        """
        if len(data) < 3:
            raise ValueError(f'AIGP TLV too short: {len(data)} bytes')
        tlv_type = data[0]
        tlv_length = unpack('!H', data[1:3])[0]
        if tlv_type != 1:
            raise ValueError(f'Unknown AIGP TLV type: {tlv_type}')
        if tlv_length != cls._TLV_LENGTH:
            raise ValueError(f'Invalid AIGP TLV length: {tlv_length}')
        if len(data) < tlv_length:
            raise ValueError(f'AIGP data truncated: got {len(data)}, expected {tlv_length}')
        return cls(data[:tlv_length])

    @classmethod
    def from_int(cls, value: int) -> 'AIGP':
        """Create AIGP from metric value.

        Args:
            value: IGP metric value (uint64)

        Returns:
            AIGP instance
        """
        return cls(cls._TLV_HEADER + pack('!Q', value))

    @property
    def aigp(self) -> int:
        """Get AIGP metric value by unpacking from bytes."""
        return unpack('!Q', self._packed[3:11])[0]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AIGP):
            return False
        return self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        if negotiated.aigp:
            return self._attribute(self._packed)
        if negotiated.local_as == negotiated.peer_as:
            return self._attribute(self._packed)
        return b''

    def __repr__(self) -> str:
        return f'0x{self.aigp:016x}'

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> AIGP | None:
        if not negotiated.aigp:
            # AIGP must only be accepted on configured sessions
            return None
        return cls.from_packet(data)
