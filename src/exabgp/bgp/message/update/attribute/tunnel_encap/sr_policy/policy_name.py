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

import json

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
        """The name a peer chose, escaped by the one thing which escapes everything.

        Replacing the quotes by hand is the half fix: a name holding a backslash ate its
        own closing quote, and a name holding a newline put a raw control character inside
        a JSON string. Both make the line unreadable to every API consumer, which is the
        corruption half of GHSA-jcrv-p53f-v5w5.
        """
        return f'"policy-name": {json.dumps(self.name)}'

    def __str__(self) -> str:
        return f'policy-name "{self.name}"'

    @classmethod
    def unpack(cls, data: Buffer) -> PolicyNameSubTLV:
        if not data:
            return cls('')
        flags = data[0]
        name = bytes(data[1:]).decode('utf-8', errors='replace')
        return cls(name=name, flags=flags)
