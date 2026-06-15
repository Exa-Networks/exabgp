"""sr_policy/policy_name.py

SR Policy Name Sub-TLV (type 129, RFC 9256 Section 2.4.7).

Wire format:
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+-- ... --+
 | Policy Name (variable, UTF-8) |
 +-+-+-+-+-+-+-+-+-- ... --+
"""

from __future__ import annotations

from struct import pack
from typing import ClassVar

from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import SubTLV
from exabgp.util.types import Buffer


@SubTLV.register(130)
class PolicyNameSubTLV(SubTLV):
    """SR Policy Name Sub-TLV (type 130, RFC 9830 Section 2.4.7)."""

    SUBTYPE: ClassVar[int] = 130

    def __init__(self, name: str, flags: int = 0) -> None:
        self.name = name
        self.flags = flags

    def pack_value(self) -> bytes:
        return pack('!B', self.flags) + self.name.encode('utf-8')

    def json(self) -> str:
        escaped = self.name.replace('"', '\\"')
        return f'"policy-name": "{escaped}"'

    def __str__(self) -> str:
        return f'policy-name "{self.name}"'

    @classmethod
    def unpack(cls, data: Buffer) -> PolicyNameSubTLV:
        if not data:
            return cls('')
        flags = data[0]
        name = bytes(data[1:]).decode('utf-8', errors='replace')
        return cls(name=name, flags=flags)
