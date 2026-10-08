"""aigp.py

Created by Thomas Mangin on 2013-09-24.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from struct import pack, unpack
from typing import ClassVar, Self, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute.attribute import Attribute, Discard
from exabgp.logger import lazymsg, log

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


class AIGPBase(Attribute):
    ID: ClassVar = Attribute.CODE.AIGP
    # RFC 7311 3.2: a malformed AIGP attribute "MUST be treated exactly as if it were an
    # unrecognized non-transitive attribute", which the RFC itself calls attribute discard.
    # This said treat-as-withdraw, which removed a route over the metric it carried.  The
    # same flag answers an AIGP sent with the transitive bit set, which 3.2 calls malformed.
    DISCARD: ClassVar[bool] = True
    FLAG: ClassVar = Attribute.Flag.OPTIONAL
    CACHING: ClassVar[bool] = True
    TYPES: ClassVar[list[int]] = [1]

    # TLV header for IGP metric: type=1, length=11 (3 header + 8 value)
    _TLV_HEADER: ClassVar[bytes] = b'\x01\x00\x0b'
    _TLV_LENGTH: ClassVar[int] = 11
    _TLV_TYPE_AIGP: ClassVar[int] = 1

    def __init__(self, packed: Buffer, metric_offset: int = 0) -> None:
        """Initialize AIGP from the packed TLVs of the attribute.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or from_int() for semantic construction.

        Args:
            packed: every TLV of the attribute, as they are passed along
            metric_offset: where the first AIGP TLV starts in packed
        """
        self._packed: Buffer = packed
        self._metric_offset = metric_offset

    @classmethod
    def from_packet(cls, data: Buffer) -> Self:
        """Validate and create from wire-format bytes.

        Args:
            data: Raw TLV bytes from wire

        Returns:
            AIGP instance

        Raises:
            ValueError: If data is malformed
        """
        # RFC 7311 section 3: the attribute is a sequence of TLVs, and only the first AIGP
        # TLV is used, but "Any other AIGP TLVs in the AIGP attribute MUST be passed along
        # unchanged".  So every TLV is walked, to refuse a broken framing, and every one is
        # kept: the attribute used to be rebuilt from the first AIGP TLV alone.  3.2 says a
        # repeated or unknown TLV does not make the attribute malformed.
        metric_offset = None
        offset = 0
        # bounded: every TLV is at least three octets, and offset only grows
        while offset < len(data):
            if len(data) - offset < 3:
                raise ValueError(f'AIGP TLV header truncated at offset {offset}')
            tlv_type = data[offset]
            tlv_length = unpack('!H', bytes(data[offset + 1 : offset + 3]))[0]
            if tlv_length < 3:
                raise ValueError(f'AIGP TLV length {tlv_length} is smaller than its own header')
            if len(data) - offset < tlv_length:
                raise ValueError(f'AIGP TLV truncated: {tlv_length} bytes announced, {len(data) - offset} available')
            if tlv_type == cls._TLV_TYPE_AIGP and metric_offset is None:
                if tlv_length != cls._TLV_LENGTH:
                    raise ValueError(f'Invalid AIGP TLV length: {tlv_length}')
                metric_offset = offset
            offset += tlv_length

        if metric_offset is None:
            raise ValueError('AIGP attribute has no AIGP TLV')

        return cls(data, metric_offset)

    @classmethod
    def from_int(cls, value: int) -> Self:
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
        start = self._metric_offset + 3
        value: int = unpack('!Q', self._packed[start : start + 8])[0]
        return value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AIGP):
            return False
        return self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self == other

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        # RFC 7311 3.3: never sent on a session for which AIGP_SESSION is disabled
        if negotiated.aigp_session:
            return self._attribute(self._packed)
        return b''

    def __repr__(self) -> str:
        return f'0x{self.aigp:016x}'

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
        if not negotiated.aigp_session:
            # RFC 7311 3.3: as an unrecognised non-transitive attribute, ignored, and logged
            # once per session rather than once per UPDATE the peer decides to send
            if not negotiated.aigp_ignored_logged:
                negotiated.aigp_ignored_logged = True
                log.info(lazymsg('attribute.aigp.ignored reason=aigp-session-disabled'), 'parser')
            return Discard(cls.ID)
        return cls.from_packet(data)


class AIGP(AIGPBase):
    """The registered form of AIGPBase, which holds the code.

    The split is not architectural: mutmut does not mutate the methods of a decorated class,
    and every decoder here carries a register decorator, so the code which parses what a
    peer sends was the one part of this tree mutation testing could not see. Keeping the
    body in an undecorated base and registering an empty subclass puts it back in reach.
    """


Attribute.register()(AIGP)
