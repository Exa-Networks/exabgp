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
When an SRv6 SID is present, value is 18 bytes: flags(1) + reserved(1) + sid(16).

MPLS Label Stack Entry (4 bytes):
  bits [31:12]: Label (top 20 bits)
  bits [11:0]:  TC, S, TTL — RESERVED per RFC 9830 Section 2.4.2, MUST be
                set to zero and MUST be ignored
"""

from __future__ import annotations

import socket
from struct import pack, unpack
from typing import ClassVar

from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import MalformedSubTLV, SubTLV
from exabgp.util.types import Buffer

# RFC 9830 Section 2.4.2 / IANA "SR Policy Binding SID Flags": only
# S-Flag (0x80, Specified-BSID-Only) and I-Flag (0x40, Drop-Upon-Invalid)
# are assigned; unassigned bits MUST be zero on transmission.
BSID_FLAG_S = 0x80
BSID_FLAG_I = 0x40

# RFC 9830 2.4.2: "The value MUST be 18 when a SRv6 BSID is present, 6 when an SR-MPLS
# BSID is present, or 2 when no BSID is present."
_BSID_NONE_SIZE = 2
_BSID_MPLS_SIZE = 6
_BSID_SRV6_SIZE = 18


class BindingSIDSubTLV(SubTLV):
    """SR Policy Binding SID Sub-TLV (MPLS)."""

    SUBTYPE: ClassVar[int] = 13

    def __init__(self, label: int | None = None, flags: int = 0, srv6_sid: str | None = None) -> None:
        """Args:
        label: MPLS label value (top 20 bits of label stack entry), None = no BSID.
        flags: Sub-TLV flags byte.
        srv6_sid: an SRv6 BSID, the form RFC 9830 2.4.2 keeps for backward compatibility.
        """
        assert label is None or srv6_sid is None, 'a binding SID is an MPLS label or an SRv6 SID, not both'
        self.label = label
        self.flags = flags
        self.srv6_sid = srv6_sid

    def pack_value(self) -> bytes:
        flags = self.flags & (BSID_FLAG_S | BSID_FLAG_I)
        if self.srv6_sid is not None:
            return pack('!BB', flags, 0) + socket.inet_pton(socket.AF_INET6, self.srv6_sid)
        if self.label is None:
            return pack('!BB', flags, 0)
        label_entry = self.label << 12  # TC/S/TTL reserved, zero on transmission (RFC 9830 2.4.2)
        return pack('!BBL', flags, 0, label_entry)

    def json(self) -> str:
        if self.srv6_sid is not None:
            return f'"binding-sid": {{"type": "srv6", "sid": "{self.srv6_sid}"}}'
        if self.label is None:
            return '"binding-sid": null'
        return f'"binding-sid": {{"type": "mpls", "label": {self.label}}}'

    def __str__(self) -> str:
        if self.srv6_sid is not None:
            return f'binding-sid srv6 {self.srv6_sid}'
        if self.label is None:
            return 'binding-sid null'
        return f'binding-sid mpls {self.label}'

    @classmethod
    def unpack(cls, data: Buffer) -> BindingSIDSubTLV:
        # Any other length used to decode to something: no BSID below two octets, a label
        # read from the first four of eighteen, and an SRv6 BSID came out as an MPLS label.
        if len(data) == _BSID_NONE_SIZE:
            return cls(label=None, flags=data[0])
        if len(data) == _BSID_MPLS_SIZE:
            label_entry: int = unpack('!L', data[2:6])[0]
            return cls(label=label_entry >> 12, flags=data[0])
        if len(data) == _BSID_SRV6_SIZE:
            return cls(srv6_sid=socket.inet_ntop(socket.AF_INET6, bytes(data[2:18])), flags=data[0])
        raise MalformedSubTLV(f'SR Policy binding SID sub-TLV is {len(data)} bytes, it must be 2, 6 or 18')


SubTLV.register(13)(BindingSIDSubTLV)
