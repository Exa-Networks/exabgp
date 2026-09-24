"""sr_policy/preference.py

SR Policy Preference Sub-TLV (type 12, RFC 9830 Section 2.4.1).

Wire format per RFC 9830:
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |     Flags     |   Reserved    |    Preference (4 octets)      |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |                Preference (continued)                         |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
Total value length: 6 bytes (Flags:1 + Reserved:1 + Preference:4).
"""

from __future__ import annotations

from struct import pack, unpack
from typing import ClassVar

from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import MalformedSubTLV, SubTLV
from exabgp.util.types import Buffer

_PREFERENCE_VALUE_SIZE = 6  # flags(1) + reserved(1) + preference(4)


@SubTLV.register(12)
class PreferenceSubTLV(SubTLV):
    """SR Policy Preference Sub-TLV."""

    SUBTYPE: ClassVar[int] = 12

    def __init__(self, preference: int, flags: int = 0) -> None:
        self.preference = preference
        self.flags = flags

    def pack_value(self) -> bytes:
        """Pack per RFC 9830: Flags(1) + Reserved(1) + Preference(4)."""
        return pack('!BBI', self.flags, 0, self.preference)

    def json(self) -> str:
        return f'"preference": {self.preference}'

    def __str__(self) -> str:
        return f'preference {self.preference}'

    @classmethod
    def unpack(cls, data: Buffer) -> PreferenceSubTLV:
        if len(data) != _PREFERENCE_VALUE_SIZE:
            # RFC 9830 2.4.1 fixes the value at six octets.  This used to return cls(0),
            # which handed the API a preference of zero the peer never sent and which a
            # consumer could not tell from a real one.  RFC 9012 13 says a malformed
            # sub-TLV is treated as an unrecognized one instead: the bytes are kept for
            # propagation and the meaning is dropped.
            raise MalformedSubTLV(
                f'SR Policy preference sub-TLV is {len(data)} bytes, it must be {_PREFERENCE_VALUE_SIZE}'
            )
        flags, reserved, preference = unpack('!BBI', data[:6])
        return cls(preference=preference, flags=flags)
