"""sr_policy/enlp.py

SR Policy Explicit NULL Label Policy Sub-TLV (type 14, RFC 9830 Section 2.4.5).

Wire format:
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)   - none defined, zero on transmission
 +-+-+-+-+-+-+-+-+
 | Reserved (1 octet) - zero on transmission
 +-+-+-+-+-+-+-+-+
 | ENLP (1 octet)
 +-+-+-+-+-+-+-+-+
Total value length: 3 bytes.

ENLP values (RFC 9830):
  1  Push IPv4 Explicit NULL only
  2  Push IPv6 Explicit NULL only
  3  Push IPv4 and IPv6 Explicit NULL
  4  Do not push Explicit NULL
"""

from __future__ import annotations

import json

from struct import pack
from typing import ClassVar

from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import SubTLV
from exabgp.util.types import Buffer

ENLP_NAMES: dict[int, str] = {
    1: 'push-ipv4',
    2: 'push-ipv6',
    3: 'push-ipv4-ipv6',
    4: 'no-push',
}
ENLP_VALUES: dict[str, int] = {name: value for value, name in ENLP_NAMES.items()}


@SubTLV.register(14)
class ENLPSubTLV(SubTLV):
    """SR Policy Explicit NULL Label Policy Sub-TLV."""

    SUBTYPE: ClassVar[int] = 14
    VALUE_SIZE: ClassVar[int] = 3  # flags(1) + reserved(1) + enlp(1)

    def __init__(self, enlp: int, flags: int = 0) -> None:
        self.enlp = enlp
        self.flags = flags

    def pack_value(self) -> bytes:
        return pack('!BBB', 0, 0, self.enlp)

    @property
    def name(self) -> str:
        """The one spelling of this ENLP value, shared by `json()` and `__str__()`.

        The two renderings used to be written out separately and had already drifted: the
        text said `no-push` where the JSON said `4`.  Anything a peer can put in that
        octet has to come back out of here, so an unassigned value falls back to its
        decimal spelling rather than raising or inventing a name for it.
        """
        return ENLP_NAMES.get(self.enlp, str(self.enlp))

    def json(self) -> str:
        """Both the wire value and its name.

        `"enlp"` keeps the integer it has always carried, because a consumer parsing it is
        entitled to keep working; `"enlp-name"` is the addition, so the API reads the way
        the text output and the configuration keyword already do.
        """
        return f'"enlp": {self.enlp}, "enlp-name": {json.dumps(self.name)}'

    def __str__(self) -> str:
        return f'enlp {self.name}'

    @classmethod
    def unpack(cls, data: Buffer) -> ENLPSubTLV:
        if len(data) < cls.VALUE_SIZE:
            return cls(0)
        return cls(enlp=data[2], flags=data[0])
