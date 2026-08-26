"""sr_policy/binding_sid.py

SR Policy Binding SID Sub-TLV (type 13, RFC 9256 Section 2.4.2).

Wire format:
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+
 | Reserved (1 octet) |
 +-+-+-+-+-+-+-+-+
 | BSID (0 or 4 octets) |
 +-+-+-+-+-+-+-+-+

When no BSID is present (explicit null), value is 2 bytes (flags + reserved only).
When an MPLS label is present, value is 6 bytes: flags(1) + reserved(1) + label_entry(4).

MPLS Label Stack Entry (4 bytes):
  bits [31:12]: Label (top 20 bits)
  bits [11:0]:  TC, S, TTL — RESERVED per RFC 9830 Section 2.4.2, MUST be
                set to zero and MUST be ignored
"""

from __future__ import annotations

from struct import pack, unpack
from typing import ClassVar

from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import SubTLV
from exabgp.util.types import Buffer

# RFC 9830 Section 2.4.2 / IANA "SR Policy Binding SID Flags": only
# S-Flag (0x80, Specified-BSID-Only) and I-Flag (0x40, Drop-Upon-Invalid)
# are assigned; unassigned bits MUST be zero on transmission.
BSID_FLAG_S = 0x80
BSID_FLAG_I = 0x40


@SubTLV.register(13)
class BindingSIDSubTLV(SubTLV):
    """SR Policy Binding SID Sub-TLV (MPLS)."""

    SUBTYPE: ClassVar[int] = 13

    def __init__(self, label: int | None = None, flags: int = 0) -> None:
        """Args:
        label: MPLS label value (top 20 bits of label stack entry), None = no BSID.
        flags: Sub-TLV flags byte.
        """
        self.label = label
        self.flags = flags

    def pack_value(self) -> bytes:
        if self.label is None:
            return pack('!BB', self.flags, 0)
        label_entry = self.label << 12  # TC/S/TTL reserved, zero on transmission (RFC 9830 2.4.2)
        return pack('!BBL', self.flags, 0, label_entry)

    def json(self) -> str:
        if self.label is None:
            return '"binding-sid": null'
        return f'"binding-sid": {{"type": "mpls", "label": {self.label}}}'

    def __str__(self) -> str:
        if self.label is None:
            return 'binding-sid null'
        return f'binding-sid mpls {self.label}'

    @classmethod
    def unpack(cls, data: Buffer) -> BindingSIDSubTLV:
        if len(data) < 2:
            return cls()
        flags = data[0]
        if len(data) >= 6:
            label_entry: int = unpack('!L', data[2:6])[0]
            label = label_entry >> 12
            return cls(label=label, flags=flags)
        return cls(label=None, flags=flags)
