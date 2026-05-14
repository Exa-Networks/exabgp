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

from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import SubTLV

# Type alias for buffer (bytes or bytearray)
Buffer = bytes | bytearray

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
        if len(data) < _PREFERENCE_VALUE_SIZE:
            return cls(0)
        flags, reserved, preference = unpack('!BBI', data[:6])
        return cls(preference=preference, flags=flags)
