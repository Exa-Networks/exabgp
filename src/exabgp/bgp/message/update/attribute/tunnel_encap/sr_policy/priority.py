"""sr_policy/priority.py

SR Policy Priority Sub-TLV (type 15, RFC 9256 Section 2.4.6).

Wire format:
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 | Priority (1 octet)            |
 | Reserved (1 octet)            |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
Total value length: 2 bytes.
"""

from __future__ import annotations

from struct import pack
from typing import ClassVar

from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import MalformedSubTLV, SubTLV
from exabgp.util.types import Buffer


class PrioritySubTLV(SubTLV):
    """SR Policy Priority Sub-TLV."""

    SUBTYPE: ClassVar[int] = 15
    VALUE_SIZE: ClassVar[int] = 2  # priority(1) + reserved(1)

    def __init__(self, priority: int) -> None:
        self.priority = priority

    def pack_value(self) -> bytes:
        return pack('!BB', self.priority, 0)

    def json(self) -> str:
        return f'"priority": {self.priority}'

    def __str__(self) -> str:
        return f'priority {self.priority}'

    @classmethod
    def unpack(cls, data: Buffer) -> PrioritySubTLV:
        # RFC 9830 2.4.6: "The value MUST be 2." An empty value used to read as priority 0.
        if len(data) != cls.VALUE_SIZE:
            raise MalformedSubTLV(f'SR Policy priority sub-TLV is {len(data)} bytes, it must be {cls.VALUE_SIZE}')
        return cls(priority=data[0])


SubTLV.register(15)(PrioritySubTLV)
