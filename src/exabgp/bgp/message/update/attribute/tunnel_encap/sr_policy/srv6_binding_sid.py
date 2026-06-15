"""sr_policy/srv6_binding_sid.py

SR Policy SRv6 Binding SID Sub-TLV (type 20, RFC 9830 Section 2.4.3).

Wire format:
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+
 | Reserved (1 octet) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SRv6 SID (16 octets)   |
 +-+-+-+-+-+-+-+-+-- ... --+
 [If B-Flag set, the following 8 bytes are appended directly:]
 | Endpoint Behavior & SID Structure (8 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+

Base value length: 18 bytes
With endpoint behavior: 26 bytes
"""

from __future__ import annotations

import socket
from struct import pack
from typing import ClassVar

from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import SubTLV
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.segment_list import SRv6EndpointBehavior
from exabgp.util.types import Buffer

_SRV6_BSID_VALUE_BASE_SIZE = 18  # flags(1) + reserved(1) + sid(16)

# SRv6 Binding SID Flags (RFC 9830 Section 2.4.3, Section 6.7)
_SRV6_BSID_FLAG_S = 0x80  # S-Flag: Specified-BSID-Only
_SRV6_BSID_FLAG_I = 0x40  # I-Flag: Drop-Upon-Invalid
_SRV6_BSID_FLAG_B = 0x20  # B-Flag: SRv6 Endpoint Behavior & SID Structure present


@SubTLV.register(20)
class SRv6BindingSIDSubTLV(SubTLV):
    """SR Policy SRv6 Binding SID Sub-TLV.

    RFC 9830 Section 2.4.3:
    When B-Flag is set, the Endpoint Behavior & SID Structure (8 bytes) is appended
    directly to the value (no Type/Length wrapper), exactly like Segment Type B.

    Value format:
      - Flags (1) + Reserved (1) + SID (16) = 18 bytes base
      - If B-Flag set: + Endpoint Behavior (8 bytes) = 26 bytes total
    """

    SUBTYPE: ClassVar[int] = 20

    def __init__(self, sid: str, flags: int = 0, endpoint_behavior: SRv6EndpointBehavior | None = None) -> None:
        """Args:
        sid: SRv6 SID as IPv6 address string.
        flags: Sub-TLV flags byte.
        endpoint_behavior: Optional SRv6 Endpoint Behavior and SID Structure.
        """
        self.sid = sid
        self.flags = flags
        self.endpoint_behavior = endpoint_behavior

    def pack_value(self) -> bytes:
        effective_flags = self.flags
        if self.endpoint_behavior is not None:
            effective_flags |= _SRV6_BSID_FLAG_B
        value = pack('!BB', effective_flags, 0) + socket.inet_pton(socket.AF_INET6, self.sid)
        if self.endpoint_behavior is not None:
            # RFC 9830: Endpoint Behavior structure appended directly (no Type/Length)
            value += self.endpoint_behavior.pack()
        return value

    def json(self) -> str:
        if self.endpoint_behavior is None:
            return f'"srv6-binding-sid": "{self.sid}"'
        eb = self.endpoint_behavior
        return (
            f'"srv6-binding-sid": {{"sid": "{self.sid}", '
            f'"behavior": {eb.endpoint_behavior}, '
            f'"lb-length": {eb.lb_length}, '
            f'"ln-length": {eb.ln_length}, '
            f'"fun-length": {eb.fun_length}, '
            f'"arg-length": {eb.arg_length}}}'
        )

    def __str__(self) -> str:
        s = f'srv6-binding-sid {self.sid}'
        if self.endpoint_behavior is not None:
            s += f' endpoint-behavior {self.endpoint_behavior.endpoint_behavior}'
        return s

    @classmethod
    def unpack(cls, data: Buffer) -> SRv6BindingSIDSubTLV:
        if len(data) < _SRV6_BSID_VALUE_BASE_SIZE:
            return cls('::')
        flags = data[0]
        sid = socket.inet_ntop(socket.AF_INET6, bytes(data[2:18]))
        endpoint_behavior: SRv6EndpointBehavior | None = None

        # RFC 9830: If B-Flag is set, Endpoint Behavior structure follows directly (no Type/Length)
        if flags & _SRV6_BSID_FLAG_B:
            remainder = data[18:]
            if len(remainder) >= SRv6EndpointBehavior.SIZE:
                endpoint_behavior = SRv6EndpointBehavior.unpack(remainder)

        return cls(sid=sid, flags=flags, endpoint_behavior=endpoint_behavior)
