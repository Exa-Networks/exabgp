"""sr_policy/segment_list.py

SR Policy Segment List Sub-TLV (type 128, RFC 9256 Section 2.4.4).

The Segment List sub-TLV contains its own set of sub-sub-TLVs.

Segment List sub-sub-TLV types:
  9   Weight
  1   Segment Type A (MPLS label only)
  3   Segment Type C (IPv4 Node Address + SR Algorithm, optionally with MPLS SID)
  4   Segment Type D (IPv6 Node Address + SR Algorithm, optionally with MPLS SID)
  5   Segment Type E (IPv4 Node Address + Local Interface ID, optionally with MPLS SID)
  6   Segment Type F (IPv4 Adjacency, optionally with MPLS SID)
  7   Segment Type G (IPv6 Link-local Adjacency with Interface IDs, optionally with MPLS SID)
  8   Segment Type H (IPv6 Adjacency, optionally with MPLS SID)
  13  Segment Type B (SRv6 SID, optionally with Endpoint Behavior sub-sub-TLV)
  14  Segment Type I (IPv6 Node Address + SR Algorithm, optionally with SRv6 SID + Endpoint Behavior)
  15  Segment Type J (IPv6 Link-local Adjacency with Interface IDs + SR Algorithm, optionally with SRv6 SID + Endpoint Behavior)
  16  Segment Type K (IPv6 Adjacency + SR Algorithm, optionally with SRv6 SID + Endpoint Behavior)
  20  SRv6 Endpoint Behavior (within Segment Type B, I, J and K)

Weight sub-sub-TLV (type 9):
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 | Reserved (3 octets)                            |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 | Weight (4 octets, unsigned)                    |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
Total value: 8 bytes.

Segment Type A sub-sub-TLV (type 1):
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+
 | Reserved (1 octet) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | MPLS Label Stack Entry (4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
Total value: 6 bytes.

Segment Type B sub-sub-TLV (type 13):
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+
 | Reserved (1 octet) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SRv6 SID (16 octets)  |
 +-+-+-+-+-+-+-+-+-- ... --+
 | [SRv6 Endpoint Behavior sub-sub-TLV (type 20, optional)] |
Total value: 18+ bytes.

Segment Type C sub-sub-TLV (type 3, RFC 9831):
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+
 | SR Algorithm (1 octet) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | IPv4 Node Address (4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SR-MPLS SID (optional, 4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
Total value: 6 bytes (without SID) or 10 bytes (with SID).

Segment Type D sub-sub-TLV (type 4, RFC 9831):
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+
 | SR Algorithm (1 octet) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | IPv6 Node Address (16 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SR-MPLS SID (optional, 4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
Total value: 18 bytes (without SID) or 22 bytes (with SID).

Segment Type E sub-sub-TLV (type 5, RFC 9831):
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+
 | Reserved (1 octet) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | Local Interface ID (4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | IPv4 Node Address (4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SR-MPLS SID (optional, 4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
Total value: 10 bytes (no SID) or 14 bytes (with SID).

Segment Type F sub-sub-TLV (type 6, RFC 9831):
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+
 | Reserved (1 octet) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | IPv4 Local Address (4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | IPv4 Remote Address (4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SR-MPLS SID (optional, 4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
Total value: 10 bytes (no SID) or 14 bytes (with SID).

Segment Type G sub-sub-TLV (type 7, RFC 9831):
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+
 | Reserved (1 octet) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | Local Interface ID (4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | IPv6 Local Node Address (16 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | Remote Interface ID (4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | IPv6 Remote Node Address (16 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SR-MPLS SID (optional, 4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
Total value: 42 bytes (no SID) or 46 bytes (with SID).

Segment Type H sub-sub-TLV (type 8, RFC 9831):
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+
 | Reserved (1 octet) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | IPv6 Local Address (16 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | IPv6 Remote Address (16 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SR-MPLS SID (optional, 4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
Total value: 34 bytes (no SID) or 38 bytes (with SID).

Segment Type I sub-sub-TLV (type 14, RFC 9831):
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+
 | SR Algorithm (1 octet) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | IPv6 Node Address (16 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SRv6 SID (optional, 16 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SRv6 Endpoint Behavior (optional, 8 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
Total value: 18 bytes (no SID), 34 bytes (SID only), or 42 bytes (SID + Endpoint Behavior).

Segment Type J sub-sub-TLV (type 15, RFC 9831):
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+
 | SR Algorithm (1 octet) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | Local Interface ID (4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | IPv6 Local Node Address (16 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | Remote Interface ID (4 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | IPv6 Remote Node Address (16 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SRv6 SID (optional, 16 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SRv6 Endpoint Behavior (optional, 8 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
Total value: 42 bytes (no SID), 58 bytes (SID only), or 66 bytes (SID + Endpoint Behavior).

Segment Type K sub-sub-TLV (type 16, RFC 9831):
 +-+-+-+-+-+-+-+-+
 | Flags (1 octet)|
 +-+-+-+-+-+-+-+-+
 | SR Algorithm (1 octet) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | Local IPv6 Address (16 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | Remote IPv6 Address (16 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SRv6 SID (optional, 16 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
 | SRv6 Endpoint Behavior (optional, 8 octets) |
 +-+-+-+-+-+-+-+-+-- ... --+
Total value: 34 bytes (no SID), 50 bytes (SID only), or 58 bytes (SID + Endpoint Behavior).

SRv6 Endpoint Behavior sub-sub-TLV (type 20, within Segment Type B, J and K):
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 | Endpoint Behavior (2 octets)  |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 | LB length (1 octet)           |
 +-+-+-+-+-+-+-+-+
 | LN length (1 octet)           |
 +-+-+-+-+-+-+-+-+
 | Fun length (1 octet)          |
 +-+-+-+-+-+-+-+-+
 | Arg length (1 octet)          |
 +-+-+-+-+-+-+-+-+
Total: 6 bytes.
"""

from __future__ import annotations

import socket
from struct import pack, unpack
from typing import ClassVar

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import SubTLV

# Type alias for buffer (bytes or bytearray)
Buffer = bytes | bytearray

# Segment Type B and C Flags (RFC 9830 Section 2.4.4.2.1, RFC 9831 Section 2.10)
# Bit layout: V|A|S|B|Rsv (bits 0-3 in RFC = bits 7-4 in byte order)
_SEG_B_FLAG_V = 0x80  # V-Flag: SID verification
_SEG_B_FLAG_A = 0x40  # A-Flag: SR Algorithm
_SEG_B_FLAG_S = 0x20  # S-Flag: SID Structure present
_SEG_B_FLAG_B = 0x10  # B-Flag: SRv6 Endpoint Behavior present

# Legacy alias for backward compatibility (corrected from 0x80 to 0x10)
_SEG_B_FLAG_ENDPOINT_BEHAVIOR = _SEG_B_FLAG_B

# Segment Type C uses the same A-Flag bit (RFC 9831 Section 2.10)
_SEG_C_FLAG_A = _SEG_B_FLAG_A  # A-Flag: SR Algorithm field is valid


class SRv6EndpointBehavior:
    """SRv6 Endpoint Behavior and Structure (sub-sub-TLV type 20 within Segment Type B).

    RFC 9830 Section 2.4.4.2.4:
    - Endpoint Behavior: 2 octets
    - Reserved: 2 octets (MUST be zero)
    - LB Length: 1 octet
    - LN Length: 1 octet
    - Function Length: 1 octet
    - Argument Length: 1 octet
    Total: 8 octets
    """

    SIZE = 8  # endpoint_behavior(2) + reserved(2) + lb(1) + ln(1) + fun(1) + arg(1)

    def __init__(
        self,
        endpoint_behavior: int,
        lb_length: int = 0,
        ln_length: int = 0,
        fun_length: int = 0,
        arg_length: int = 0,
    ) -> None:
        self.endpoint_behavior = endpoint_behavior
        self.lb_length = lb_length
        self.ln_length = ln_length
        self.fun_length = fun_length
        self.arg_length = arg_length

    def pack(self) -> bytes:
        # RFC 9830: Endpoint Behavior (2) + Reserved (2) + LB/LN/Fun/Arg (1 each)
        return pack(
            '!HHBBBB', self.endpoint_behavior, 0, self.lb_length, self.ln_length, self.fun_length, self.arg_length
        )

    def json(self) -> str:
        return (
            '"endpoint-behavior": {'
            f'"behavior": {self.endpoint_behavior}, '
            f'"lb-length": {self.lb_length}, '
            f'"ln-length": {self.ln_length}, '
            f'"fun-length": {self.fun_length}, '
            f'"arg-length": {self.arg_length}'
            '}'
        )

    @classmethod
    def unpack(cls, data: Buffer) -> SRv6EndpointBehavior:
        if len(data) < cls.SIZE:
            return cls(0)
        # RFC 9830: Endpoint Behavior (2) + Reserved (2) + LB/LN/Fun/Arg (1 each)
        eb, reserved, lb, ln, fun, arg = unpack('!HHBBBB', data[: cls.SIZE])
        # reserved is ignored per RFC
        return cls(endpoint_behavior=eb, lb_length=lb, ln_length=ln, fun_length=fun, arg_length=arg)


class WeightSubSubTLV:
    """Segment List Weight sub-sub-TLV (type 9).

    RFC 9830 Section 2.4.4.1:
    Wire format: Flags(1) + Reserved(1) + Weight(4) = 6 bytes total value.
    """

    SUBTYPE: ClassVar[int] = 9
    VALUE_SIZE: ClassVar[int] = 6  # flags(1) + reserved(1) + weight(4)

    def __init__(self, weight: int, flags: int = 0) -> None:
        self.weight = weight
        self.flags = flags

    def pack(self) -> bytes:
        """Pack per RFC 9830: Flags(1) + Reserved(1) + Weight(4)."""
        value = pack('!BBI', self.flags, 0, self.weight)
        return pack('!BB', self.SUBTYPE, len(value)) + value

    def json(self) -> str:
        return f'"weight": {self.weight}'

    @classmethod
    def unpack(cls, data: Buffer) -> WeightSubSubTLV:
        if len(data) < cls.VALUE_SIZE:
            return cls(1)
        flags, reserved, weight = unpack('!BBI', data[:6])
        return cls(weight=weight, flags=flags)


class SegmentTypeA:
    """Segment Type A: MPLS label only (sub-sub-TLV type 1).

    RFC 3032: The S-bit (bottom-of-stack) is set to 1 for the last entry
    in the label stack, and 0 for all other entries.
    """

    SUBTYPE: ClassVar[int] = 1
    VALUE_SIZE: ClassVar[int] = 6  # flags(1) + reserved(1) + label_entry(4)

    def __init__(self, label: int, flags: int = 0, tc: int = 0, s: bool = False, ttl: int = 0) -> None:
        """
        Args:
            label: MPLS label value (20 bits)
            flags: Segment flags
            tc: Traffic class (3 bits)
            s: Bottom-of-stack bit (default False, set by SegmentListSubTLV.pack_value())
            ttl: Time-to-live (8 bits)
        """
        self.label = label
        self.flags = flags
        self.tc = tc
        self.s = s
        self.ttl = ttl

    def pack(self, is_last: bool = False) -> bytes:
        """Pack the segment.

        Args:
            is_last: If True, sets the S-bit (bottom-of-stack). This is typically
                     set by SegmentListSubTLV.pack_value() for the last Type A segment.
        """
        s_bit = is_last or self.s  # Use is_last parameter or explicit s value
        label_entry = (self.label << 12) | (self.tc << 9) | (0x100 if s_bit else 0) | self.ttl
        value = pack('!BBL', self.flags, 0, label_entry)
        return pack('!BB', self.SUBTYPE, len(value)) + value

    def json(self) -> str:
        return f'{{"type": "A", "label": {self.label}, "tc": {self.tc}, "s": {str(self.s).lower()}, "ttl": {self.ttl}}}'

    @classmethod
    def unpack(cls, data: Buffer) -> SegmentTypeA:
        if len(data) < cls.VALUE_SIZE:
            return cls(0)
        flags = data[0]
        label_entry: int = unpack('!L', data[2:6])[0]
        label = label_entry >> 12
        tc = (label_entry >> 9) & 0x7
        s = bool(label_entry & 0x100)
        ttl = label_entry & 0xFF
        return cls(label=label, flags=flags, tc=tc, s=s, ttl=ttl)


class SegmentTypeB:
    """Segment Type B: SRv6 SID (sub-sub-TLV type 13), optionally with endpoint behavior.

    RFC 9830 Section 2.4.4.2.1:
    When B-Flag is set, the Endpoint Behavior structure (8 bytes) is appended
    directly to the value (no additional Type/Length wrapper).

    Value format:
      - Flags (1) + Reserved (1) + SID (16) = 18 bytes base
      - If B-Flag set: + Endpoint Behavior (8 bytes) = 26 bytes total
    """

    SUBTYPE: ClassVar[int] = 13
    VALUE_BASE_SIZE: ClassVar[int] = 18  # flags(1) + reserved(1) + sid(16)

    def __init__(
        self,
        sid: str,
        flags: int = 0,
        endpoint_behavior: SRv6EndpointBehavior | None = None,
    ) -> None:
        self.sid = sid
        self.flags = flags
        self.endpoint_behavior = endpoint_behavior

    def pack(self, is_last: bool = False) -> bytes:
        """Pack the segment.

        Args:
            is_last: Unused for Type B (SRv6 has no bottom-of-stack bit).
                     Included for API consistency with SegmentTypeA.
        """
        sid_bytes = socket.inet_pton(socket.AF_INET6, self.sid)
        effective_flags = self.flags
        if self.endpoint_behavior is not None:
            effective_flags |= _SEG_B_FLAG_B
        value = pack('!BB', effective_flags, 0) + sid_bytes
        if self.endpoint_behavior is not None:
            # RFC 9830: Endpoint Behavior structure appended directly (no Type/Length)
            value += self.endpoint_behavior.pack()
        return pack('!BB', self.SUBTYPE, len(value)) + value

    def json(self) -> str:
        parts = ['"type": "B"', f'"sid": "{self.sid}"']
        if self.endpoint_behavior is not None:
            parts.append(self.endpoint_behavior.json())
        return '{' + ', '.join(parts) + '}'

    @classmethod
    def unpack(cls, data: Buffer) -> SegmentTypeB:
        if len(data) < cls.VALUE_BASE_SIZE:
            return cls('::')
        flags = data[0]
        sid = socket.inet_ntop(socket.AF_INET6, bytes(data[2:18]))
        endpoint_behavior: SRv6EndpointBehavior | None = None

        # RFC 9830: If B-Flag is set, Endpoint Behavior structure follows directly (no Type/Length)
        if flags & _SEG_B_FLAG_B:
            remainder = data[18:]
            if len(remainder) >= SRv6EndpointBehavior.SIZE:
                endpoint_behavior = SRv6EndpointBehavior.unpack(remainder)

        return cls(sid=sid, flags=flags, endpoint_behavior=endpoint_behavior)


class SegmentTypeC:
    """Segment Type C: IPv4 Node Address + SR Algorithm + optional MPLS SID (sub-sub-TLV type 3).

    RFC 9831 Section 2.1:
    Value format:
      - Flags (1 octet)
      - SR Algorithm (1 octet) - valid when A-Flag is set
      - IPv4 Node Address (4 octets)
      - SR-MPLS SID (optional, 4 octets) - same format as Type A label stack entry

    Length:
      - 6 octets when SR-MPLS SID is absent
      - 10 octets when SR-MPLS SID is present
    """

    SUBTYPE: ClassVar[int] = 3
    VALUE_BASE_SIZE: ClassVar[int] = 6  # flags(1) + algorithm(1) + ipv4(4)
    VALUE_WITH_SID_SIZE: ClassVar[int] = 10  # base + sid(4)

    def __init__(
        self,
        ipv4_node: str,
        algorithm: int = 0,
        flags: int = 0,
        sid: int | None = None,
        tc: int = 0,
        s: bool = False,
        ttl: int = 0,
    ) -> None:
        """
        Args:
            ipv4_node: IPv4 address representing a node
            algorithm: SR Algorithm (valid when A-Flag is set)
            flags: Segment flags (A-Flag = 0x40 when algorithm is valid)
            sid: Optional MPLS label value (20 bits)
            tc: Traffic class for MPLS SID (3 bits)
            s: Bottom-of-stack bit for MPLS SID
            ttl: Time-to-live for MPLS SID (8 bits)
        """
        self.ipv4_node = ipv4_node
        self.algorithm = algorithm
        self.flags = flags
        self.sid = sid
        self.tc = tc
        self.s = s
        self.ttl = ttl

    def pack(self, is_last: bool = False) -> bytes:
        """Pack the segment.

        Args:
            is_last: If True and sid is present, sets the S-bit (bottom-of-stack).
        """
        ipv4_bytes = socket.inet_pton(socket.AF_INET, self.ipv4_node)
        value = pack('!BB', self.flags, self.algorithm) + ipv4_bytes

        if self.sid is not None:
            s_bit = is_last or self.s
            label_entry = (self.sid << 12) | (self.tc << 9) | (0x100 if s_bit else 0) | self.ttl
            value += pack('!L', label_entry)

        return pack('!BB', self.SUBTYPE, len(value)) + value

    def json(self) -> str:
        parts = [
            '"type": "C"',
            f'"ipv4_node": "{self.ipv4_node}"',
            f'"algorithm": {self.algorithm}',
        ]
        if self.sid is not None:
            parts.extend(
                [
                    f'"sid": {self.sid}',
                    f'"tc": {self.tc}',
                    f'"s": {str(self.s).lower()}',
                    f'"ttl": {self.ttl}',
                ]
            )
        return '{' + ', '.join(parts) + '}'

    @classmethod
    def unpack(cls, data: Buffer) -> SegmentTypeC:
        if len(data) < cls.VALUE_BASE_SIZE:
            return cls('0.0.0.0')

        flags = data[0]
        algorithm = data[1]
        ipv4_node = socket.inet_ntop(socket.AF_INET, bytes(data[2:6]))

        sid = None
        tc = 0
        s = False
        ttl = 0

        # Check if SR-MPLS SID is present (length == 10)
        if len(data) >= cls.VALUE_WITH_SID_SIZE:
            label_entry: int = unpack('!L', data[6:10])[0]
            sid = label_entry >> 12
            tc = (label_entry >> 9) & 0x7
            s = bool(label_entry & 0x100)
            ttl = label_entry & 0xFF

        return cls(
            ipv4_node=ipv4_node,
            algorithm=algorithm,
            flags=flags,
            sid=sid,
            tc=tc,
            s=s,
            ttl=ttl,
        )


class SegmentTypeD:
    """Segment Type D: IPv6 Node Address + SR Algorithm + optional MPLS SID (sub-sub-TLV type 4).

    RFC 9831 Section 2.2:
    IPv6 equivalent of Type C - combines IPv6 node address with SR algorithm and optional MPLS SID.

    Value format:
      - Flags (1 octet)
      - SR Algorithm (1 octet)
      - IPv6 Node Address (16 octets)
      - SR-MPLS SID (optional, 4 octets)

    Length:
      - 18 octets when SR-MPLS SID is absent
      - 22 octets when SR-MPLS SID is present
    """

    SUBTYPE: ClassVar[int] = 4
    VALUE_BASE_SIZE: ClassVar[int] = 18  # flags(1) + algorithm(1) + ipv6(16)
    VALUE_WITH_SID_SIZE: ClassVar[int] = 22  # base + mpls_sid(4)

    def __init__(
        self,
        ipv6_node: str,
        algorithm: int = 0,
        flags: int = 0,
        sid: int | None = None,
        tc: int = 0,
        s: bool = False,
        ttl: int = 0,
    ) -> None:
        """
        Args:
            ipv6_node: IPv6 node address
            algorithm: SR Algorithm (1 octet)
            flags: Segment flags (A-Flag should be set if algorithm != 0)
            sid: Optional MPLS label (20 bits)
            tc: Traffic class (3 bits)
            s: Bottom-of-stack bit
            ttl: Time to live (8 bits)
        """
        self.ipv6_node = ipv6_node
        self.algorithm = algorithm
        self.flags = flags
        self.sid = sid
        self.tc = tc
        self.s = s
        self.ttl = ttl

    def pack(self, is_last: bool = False) -> bytes:
        """Pack the segment.

        Args:
            is_last: If True and sid is present, sets the S-bit (bottom of stack).
        """
        ipv6_bytes = socket.inet_pton(socket.AF_INET6, self.ipv6_node)

        value = pack('!BB', self.flags, self.algorithm)
        value += ipv6_bytes

        if self.sid is not None:
            # Pack MPLS label entry: label(20) + tc(3) + s(1) + ttl(8)
            effective_s = is_last or self.s
            label_entry = (self.sid << 12) | (self.tc << 9) | (effective_s << 8) | self.ttl
            value += pack('!L', label_entry)

        return pack('!BB', self.SUBTYPE, len(value)) + value

    def json(self) -> str:
        parts = [
            '"type": "D"',
            f'"ipv6_node": "{self.ipv6_node}"',
            f'"algorithm": {self.algorithm}',
        ]
        if self.sid is not None:
            parts.append(f'"sid": {self.sid}')
        return '{' + ', '.join(parts) + '}'

    @classmethod
    def unpack(cls, data: Buffer) -> SegmentTypeD:
        if len(data) < cls.VALUE_BASE_SIZE:
            return cls('::', 0)

        flags = data[0]
        algorithm = data[1]
        ipv6_node = socket.inet_ntop(socket.AF_INET6, bytes(data[2:18]))

        sid = None
        tc = 0
        s = False
        ttl = 0

        # Check if MPLS SID is present (length == 22)
        if len(data) >= cls.VALUE_WITH_SID_SIZE:
            label_entry: int = unpack('!L', data[18:22])[0]
            sid = label_entry >> 12
            tc = (label_entry >> 9) & 0x7
            s = bool(label_entry & 0x100)
            ttl = label_entry & 0xFF

        return cls(
            ipv6_node=ipv6_node,
            algorithm=algorithm,
            flags=flags,
            sid=sid,
            tc=tc,
            s=s,
            ttl=ttl,
        )


class SegmentTypeE:
    """Segment Type E: IPv4 Node Address + Local Interface ID + optional MPLS SID (sub-sub-TLV type 5).

    RFC 9831 Section 2.3:
    Combines IPv4 node address with interface ID and optional MPLS SID.

    Value format:
      - Flags (1 octet)
      - Reserved (1 octet)
      - Local Interface ID (4 octets)
      - IPv4 Node Address (4 octets)
      - SR-MPLS SID (optional, 4 octets)

    Length:
      - 10 octets when SR-MPLS SID is absent
      - 14 octets when SR-MPLS SID is present
    """

    SUBTYPE: ClassVar[int] = 5
    VALUE_BASE_SIZE: ClassVar[int] = 10  # flags(1) + reserved(1) + if_id(4) + ipv4(4)
    VALUE_WITH_SID_SIZE: ClassVar[int] = 14  # base + mpls_sid(4)

    def __init__(
        self,
        local_if_id: int,
        ipv4_node: str,
        flags: int = 0,
        sid: int | None = None,
        tc: int = 0,
        s: bool = False,
        ttl: int = 0,
    ) -> None:
        """
        Args:
            local_if_id: Local interface ID (4 octets)
            ipv4_node: IPv4 node address
            flags: Segment flags
            sid: Optional MPLS label (20 bits)
            tc: Traffic class (3 bits)
            s: Bottom-of-stack bit
            ttl: Time to live (8 bits)
        """
        self.local_if_id = local_if_id
        self.ipv4_node = ipv4_node
        self.flags = flags
        self.sid = sid
        self.tc = tc
        self.s = s
        self.ttl = ttl

    def pack(self, is_last: bool = False) -> bytes:
        """Pack the segment.

        Args:
            is_last: If True and sid is present, sets the S-bit (bottom of stack).
        """
        ipv4_bytes = socket.inet_pton(socket.AF_INET, self.ipv4_node)

        value = pack('!BB', self.flags, 0)  # flags + reserved
        value += pack('!L', self.local_if_id)
        value += ipv4_bytes

        if self.sid is not None:
            # Pack MPLS label entry: label(20) + tc(3) + s(1) + ttl(8)
            effective_s = is_last or self.s
            label_entry = (self.sid << 12) | (self.tc << 9) | (effective_s << 8) | self.ttl
            value += pack('!L', label_entry)

        return pack('!BB', self.SUBTYPE, len(value)) + value

    def json(self) -> str:
        parts = [
            '"type": "E"',
            f'"local_if_id": {self.local_if_id}',
            f'"ipv4_node": "{self.ipv4_node}"',
        ]
        if self.sid is not None:
            parts.append(f'"sid": {self.sid}')
        return '{' + ', '.join(parts) + '}'

    @classmethod
    def unpack(cls, data: Buffer) -> SegmentTypeE:
        if len(data) < cls.VALUE_BASE_SIZE:
            return cls(0, '0.0.0.0')

        flags = data[0]
        # data[1] is reserved
        local_if_id = unpack('!L', bytes(data[2:6]))[0]
        ipv4_node = socket.inet_ntop(socket.AF_INET, bytes(data[6:10]))

        sid = None
        tc = 0
        s = False
        ttl = 0

        # Check if MPLS SID is present (length == 14)
        if len(data) >= cls.VALUE_WITH_SID_SIZE:
            label_entry: int = unpack('!L', data[10:14])[0]
            sid = label_entry >> 12
            tc = (label_entry >> 9) & 0x7
            s = bool(label_entry & 0x100)
            ttl = label_entry & 0xFF

        return cls(
            local_if_id=local_if_id,
            ipv4_node=ipv4_node,
            flags=flags,
            sid=sid,
            tc=tc,
            s=s,
            ttl=ttl,
        )


class SegmentTypeF:
    """Segment Type F: IPv4 Adjacency + optional MPLS SID (sub-sub-TLV type 6).

    RFC 9831 Section 2.4:
    IPv4 equivalent of Type H. Both provide adjacency with optional MPLS SID.

    Value format:
      - Flags (1 octet)
      - Reserved (1 octet)
      - IPv4 Local Address (4 octets)
      - IPv4 Remote Address (4 octets)
      - SR-MPLS SID (optional, 4 octets)

    Length:
      - 10 octets when SR-MPLS SID is absent
      - 14 octets when SR-MPLS SID is present
    """

    SUBTYPE: ClassVar[int] = 6
    VALUE_BASE_SIZE: ClassVar[int] = 10  # flags(1) + reserved(1) + local_ipv4(4) + remote_ipv4(4)
    VALUE_WITH_SID_SIZE: ClassVar[int] = 14  # base + mpls_sid(4)

    def __init__(
        self,
        local_ipv4: str,
        remote_ipv4: str,
        flags: int = 0,
        sid: int | None = None,
        tc: int = 0,
        s: bool = False,
        ttl: int = 0,
    ) -> None:
        """
        Args:
            local_ipv4: IPv4 local address
            remote_ipv4: IPv4 remote address
            flags: Segment flags
            sid: Optional MPLS label (20 bits)
            tc: Traffic class (3 bits)
            s: Bottom-of-stack bit
            ttl: Time to live (8 bits)
        """
        self.local_ipv4 = local_ipv4
        self.remote_ipv4 = remote_ipv4
        self.flags = flags
        self.sid = sid
        self.tc = tc
        self.s = s
        self.ttl = ttl

    def pack(self, is_last: bool = False) -> bytes:
        """Pack the segment.

        Args:
            is_last: If True and sid is present, sets the S-bit (bottom of stack).
        """
        local_ipv4_bytes = socket.inet_pton(socket.AF_INET, self.local_ipv4)
        remote_ipv4_bytes = socket.inet_pton(socket.AF_INET, self.remote_ipv4)

        value = pack('!BB', self.flags, 0)  # flags + reserved
        value += local_ipv4_bytes
        value += remote_ipv4_bytes

        if self.sid is not None:
            # Pack MPLS label entry: label(20) + tc(3) + s(1) + ttl(8)
            effective_s = is_last or self.s
            label_entry = (self.sid << 12) | (self.tc << 9) | (effective_s << 8) | self.ttl
            value += pack('!L', label_entry)

        return pack('!BB', self.SUBTYPE, len(value)) + value

    def json(self) -> str:
        parts = [
            '"type": "F"',
            f'"local_ipv4": "{self.local_ipv4}"',
            f'"remote_ipv4": "{self.remote_ipv4}"',
        ]
        if self.sid is not None:
            parts.append(f'"sid": {self.sid}')
        return '{' + ', '.join(parts) + '}'

    @classmethod
    def unpack(cls, data: Buffer) -> SegmentTypeF:
        if len(data) < cls.VALUE_BASE_SIZE:
            return cls('0.0.0.0', '0.0.0.0')

        flags = data[0]
        # data[1] is reserved
        local_ipv4 = socket.inet_ntop(socket.AF_INET, bytes(data[2:6]))
        remote_ipv4 = socket.inet_ntop(socket.AF_INET, bytes(data[6:10]))

        sid = None
        tc = 0
        s = False
        ttl = 0

        # Check if MPLS SID is present (length == 14)
        if len(data) >= cls.VALUE_WITH_SID_SIZE:
            label_entry: int = unpack('!L', data[10:14])[0]
            sid = label_entry >> 12
            tc = (label_entry >> 9) & 0x7
            s = bool(label_entry & 0x100)
            ttl = label_entry & 0xFF

        return cls(
            local_ipv4=local_ipv4,
            remote_ipv4=remote_ipv4,
            flags=flags,
            sid=sid,
            tc=tc,
            s=s,
            ttl=ttl,
        )


class SegmentTypeG:
    """Segment Type G: IPv6 Link-local Adjacency with Interface IDs + optional MPLS SID (sub-sub-TLV type 7).

    RFC 9831 Section 2.5:
    Similar to Type J but uses MPLS SID instead of SRv6 SID.

    Value format:
      - Flags (1 octet)
      - Reserved (1 octet)
      - Local Interface ID (4 octets)
      - IPv6 Local Node Address (16 octets)
      - Remote Interface ID (4 octets)
      - IPv6 Remote Node Address (16 octets)
      - SR-MPLS SID (optional, 4 octets)

    Length:
      - 42 octets when SR-MPLS SID is absent
      - 46 octets when SR-MPLS SID is present
    """

    SUBTYPE: ClassVar[int] = 7
    VALUE_BASE_SIZE: ClassVar[int] = (
        42  # flags(1) + reserved(1) + local_if(4) + local_ipv6(16) + remote_if(4) + remote_ipv6(16)
    )
    VALUE_WITH_SID_SIZE: ClassVar[int] = 46  # base + mpls_sid(4)

    def __init__(
        self,
        local_if_id: int,
        local_ipv6: str,
        remote_if_id: int,
        remote_ipv6: str,
        flags: int = 0,
        sid: int | None = None,
        tc: int = 0,
        s: bool = False,
        ttl: int = 0,
    ) -> None:
        """
        Args:
            local_if_id: Local interface ID (4 octets)
            local_ipv6: IPv6 local node address
            remote_if_id: Remote interface ID (4 octets, may be 0)
            remote_ipv6: IPv6 remote node address (may be ::0)
            flags: Segment flags
            sid: Optional MPLS label (20 bits)
            tc: Traffic class (3 bits)
            s: Bottom-of-stack bit
            ttl: Time to live (8 bits)
        """
        self.local_if_id = local_if_id
        self.local_ipv6 = local_ipv6
        self.remote_if_id = remote_if_id
        self.remote_ipv6 = remote_ipv6
        self.flags = flags
        self.sid = sid
        self.tc = tc
        self.s = s
        self.ttl = ttl

    def pack(self, is_last: bool = False) -> bytes:
        """Pack the segment.

        Args:
            is_last: If True and sid is present, sets the S-bit (bottom of stack).
        """
        local_ipv6_bytes = socket.inet_pton(socket.AF_INET6, self.local_ipv6)
        remote_ipv6_bytes = socket.inet_pton(socket.AF_INET6, self.remote_ipv6)

        value = pack('!BB', self.flags, 0)  # flags + reserved
        value += pack('!L', self.local_if_id)
        value += local_ipv6_bytes
        value += pack('!L', self.remote_if_id)
        value += remote_ipv6_bytes

        if self.sid is not None:
            # Pack MPLS label entry: label(20) + tc(3) + s(1) + ttl(8)
            effective_s = is_last or self.s
            label_entry = (self.sid << 12) | (self.tc << 9) | (effective_s << 8) | self.ttl
            value += pack('!L', label_entry)

        return pack('!BB', self.SUBTYPE, len(value)) + value

    def json(self) -> str:
        parts = [
            '"type": "G"',
            f'"local_if_id": {self.local_if_id}',
            f'"local_ipv6": "{self.local_ipv6}"',
            f'"remote_if_id": {self.remote_if_id}',
            f'"remote_ipv6": "{self.remote_ipv6}"',
        ]
        if self.sid is not None:
            parts.append(f'"sid": {self.sid}')
        return '{' + ', '.join(parts) + '}'

    @classmethod
    def unpack(cls, data: Buffer) -> SegmentTypeG:
        if len(data) < cls.VALUE_BASE_SIZE:
            return cls(0, '::', 0, '::')

        flags = data[0]
        # data[1] is reserved
        local_if_id = unpack('!L', bytes(data[2:6]))[0]
        local_ipv6 = socket.inet_ntop(socket.AF_INET6, bytes(data[6:22]))
        remote_if_id = unpack('!L', bytes(data[22:26]))[0]
        remote_ipv6 = socket.inet_ntop(socket.AF_INET6, bytes(data[26:42]))

        sid = None
        tc = 0
        s = False
        ttl = 0

        # Check if MPLS SID is present (length == 46)
        if len(data) >= cls.VALUE_WITH_SID_SIZE:
            label_entry: int = unpack('!L', data[42:46])[0]
            sid = label_entry >> 12
            tc = (label_entry >> 9) & 0x7
            s = bool(label_entry & 0x100)
            ttl = label_entry & 0xFF

        return cls(
            local_if_id=local_if_id,
            local_ipv6=local_ipv6,
            remote_if_id=remote_if_id,
            remote_ipv6=remote_ipv6,
            flags=flags,
            sid=sid,
            tc=tc,
            s=s,
            ttl=ttl,
        )


class SegmentTypeH:
    """Segment Type H: IPv6 Adjacency + optional MPLS SID (sub-sub-TLV type 8).

    RFC 9831 Section 2.6:
    Similar to Type K but uses MPLS SID instead of SRv6 SID.
    Similar to Type G but without interface IDs.

    Value format:
      - Flags (1 octet)
      - Reserved (1 octet)
      - IPv6 Local Address (16 octets)
      - IPv6 Remote Address (16 octets)
      - SR-MPLS SID (optional, 4 octets)

    Length:
      - 34 octets when SR-MPLS SID is absent
      - 38 octets when SR-MPLS SID is present
    """

    SUBTYPE: ClassVar[int] = 8
    VALUE_BASE_SIZE: ClassVar[int] = 34  # flags(1) + reserved(1) + local_ipv6(16) + remote_ipv6(16)
    VALUE_WITH_SID_SIZE: ClassVar[int] = 38  # base + mpls_sid(4)

    def __init__(
        self,
        local_ipv6: str,
        remote_ipv6: str,
        flags: int = 0,
        sid: int | None = None,
        tc: int = 0,
        s: bool = False,
        ttl: int = 0,
    ) -> None:
        """
        Args:
            local_ipv6: IPv6 local address
            remote_ipv6: IPv6 remote address
            flags: Segment flags
            sid: Optional MPLS label (20 bits)
            tc: Traffic class (3 bits)
            s: Bottom-of-stack bit
            ttl: Time to live (8 bits)
        """
        self.local_ipv6 = local_ipv6
        self.remote_ipv6 = remote_ipv6
        self.flags = flags
        self.sid = sid
        self.tc = tc
        self.s = s
        self.ttl = ttl

    def pack(self, is_last: bool = False) -> bytes:
        """Pack the segment.

        Args:
            is_last: If True and sid is present, sets the S-bit (bottom of stack).
        """
        local_ipv6_bytes = socket.inet_pton(socket.AF_INET6, self.local_ipv6)
        remote_ipv6_bytes = socket.inet_pton(socket.AF_INET6, self.remote_ipv6)

        value = pack('!BB', self.flags, 0)  # flags + reserved
        value += local_ipv6_bytes
        value += remote_ipv6_bytes

        if self.sid is not None:
            # Pack MPLS label entry: label(20) + tc(3) + s(1) + ttl(8)
            effective_s = is_last or self.s
            label_entry = (self.sid << 12) | (self.tc << 9) | (effective_s << 8) | self.ttl
            value += pack('!L', label_entry)

        return pack('!BB', self.SUBTYPE, len(value)) + value

    def json(self) -> str:
        parts = [
            '"type": "H"',
            f'"local_ipv6": "{self.local_ipv6}"',
            f'"remote_ipv6": "{self.remote_ipv6}"',
        ]
        if self.sid is not None:
            parts.append(f'"sid": {self.sid}')
        return '{' + ', '.join(parts) + '}'

    @classmethod
    def unpack(cls, data: Buffer) -> SegmentTypeH:
        if len(data) < cls.VALUE_BASE_SIZE:
            return cls('::', '::')

        flags = data[0]
        # data[1] is reserved
        local_ipv6 = socket.inet_ntop(socket.AF_INET6, bytes(data[2:18]))
        remote_ipv6 = socket.inet_ntop(socket.AF_INET6, bytes(data[18:34]))

        sid = None
        tc = 0
        s = False
        ttl = 0

        # Check if MPLS SID is present (length == 38)
        if len(data) >= cls.VALUE_WITH_SID_SIZE:
            label_entry: int = unpack('!L', data[34:38])[0]
            sid = label_entry >> 12
            tc = (label_entry >> 9) & 0x7
            s = bool(label_entry & 0x100)
            ttl = label_entry & 0xFF

        return cls(
            local_ipv6=local_ipv6,
            remote_ipv6=remote_ipv6,
            flags=flags,
            sid=sid,
            tc=tc,
            s=s,
            ttl=ttl,
        )


class SegmentTypeI:
    """Segment Type I: IPv6 Node Address + SR Algorithm + optional SRv6 SID + Endpoint Behavior (sub-sub-TLV type 14).

    RFC 9831 Section 2.7:
    This is the IPv6 equivalent of Type C (which is IPv4).

    Value format:
      - Flags (1 octet)
      - SR Algorithm (1 octet) - valid when A-Flag is set
      - IPv6 Node Address (16 octets)
      - SRv6 SID (optional, 16 octets)
      - SRv6 Endpoint Behavior (optional, 8 octets) - only when SID is present

    Length:
      - 18 octets when SRv6 SID is absent
      - 34 octets when SRv6 SID is present (without Endpoint Behavior)
      - 42 octets when both SRv6 SID and Endpoint Behavior are present
    """

    SUBTYPE: ClassVar[int] = 14
    VALUE_BASE_SIZE: ClassVar[int] = 18  # flags(1) + algorithm(1) + ipv6(16)
    VALUE_WITH_SID_SIZE: ClassVar[int] = 34  # base + sid(16)
    VALUE_WITH_EB_SIZE: ClassVar[int] = 42  # base + sid(16) + endpoint_behavior(8)

    def __init__(
        self,
        ipv6_node: str,
        algorithm: int = 0,
        flags: int = 0,
        sid: str | None = None,
        endpoint_behavior: SRv6EndpointBehavior | None = None,
    ) -> None:
        """
        Args:
            ipv6_node: IPv6 address representing the node
            algorithm: SR Algorithm (valid when A-Flag is set)
            flags: Segment flags (A-Flag = 0x40, B-Flag = 0x10 for endpoint behavior)
            sid: Optional SRv6 SID (IPv6 address, can be ::0)
            endpoint_behavior: Optional SRv6 Endpoint Behavior (only if sid is present)
        """
        self.ipv6_node = ipv6_node
        self.algorithm = algorithm
        self.flags = flags
        self.sid = sid
        self.endpoint_behavior = endpoint_behavior

    def pack(self, is_last: bool = False) -> bytes:
        """Pack the segment.

        Args:
            is_last: Unused for Type I (SRv6 has no bottom-of-stack bit).
                     Included for API consistency.
        """
        ipv6_bytes = socket.inet_pton(socket.AF_INET6, self.ipv6_node)

        effective_flags = self.flags
        if self.endpoint_behavior is not None:
            effective_flags |= _SEG_B_FLAG_B  # Set B-Flag

        value = pack('!BB', effective_flags, self.algorithm) + ipv6_bytes

        if self.sid is not None:
            sid_bytes = socket.inet_pton(socket.AF_INET6, self.sid)
            value += sid_bytes

            # Endpoint Behavior can only be present if SID is present
            if self.endpoint_behavior is not None:
                value += self.endpoint_behavior.pack()

        return pack('!BB', self.SUBTYPE, len(value)) + value

    def json(self) -> str:
        parts = [
            '"type": "I"',
            f'"ipv6_node": "{self.ipv6_node}"',
            f'"algorithm": {self.algorithm}',
        ]
        if self.sid is not None:
            parts.append(f'"sid": "{self.sid}"')
        if self.endpoint_behavior is not None:
            parts.append(self.endpoint_behavior.json())
        return '{' + ', '.join(parts) + '}'

    @classmethod
    def unpack(cls, data: Buffer) -> SegmentTypeI:
        if len(data) < cls.VALUE_BASE_SIZE:
            return cls('::')

        flags = data[0]
        algorithm = data[1]
        ipv6_node = socket.inet_ntop(socket.AF_INET6, bytes(data[2:18]))

        sid = None
        endpoint_behavior: SRv6EndpointBehavior | None = None

        # Check if SRv6 SID is present (length >= 34)
        if len(data) >= cls.VALUE_WITH_SID_SIZE:
            sid = socket.inet_ntop(socket.AF_INET6, bytes(data[18:34]))

            # Check if Endpoint Behavior is present (length >= 42 and B-Flag set)
            if len(data) >= cls.VALUE_WITH_EB_SIZE and (flags & _SEG_B_FLAG_B):
                endpoint_behavior = SRv6EndpointBehavior.unpack(data[34:42])

        return cls(
            ipv6_node=ipv6_node,
            algorithm=algorithm,
            flags=flags,
            sid=sid,
            endpoint_behavior=endpoint_behavior,
        )


class SegmentTypeJ:
    """Segment Type J: IPv6 Link-local Adjacency with Interface IDs + SR Algorithm + optional SRv6 SID + EB (sub-sub-TLV type 15).

    RFC 9831 Section 2.8:
    Value format:
      - Flags (1 octet)
      - SR Algorithm (1 octet) - valid when A-Flag is set
      - Local Interface ID (4 octets)
      - IPv6 Local Node Address (16 octets)
      - Remote Interface ID (4 octets)
      - IPv6 Remote Node Address (16 octets)
      - SRv6 SID (optional, 16 octets)
      - SRv6 Endpoint Behavior (optional, 8 octets) - only when SID is present

    Length:
      - 42 octets when SRv6 SID is absent
      - 58 octets when SRv6 SID is present (without Endpoint Behavior)
      - 66 octets when both SRv6 SID and Endpoint Behavior are present
    """

    SUBTYPE: ClassVar[int] = 15
    VALUE_BASE_SIZE: ClassVar[int] = (
        42  # flags(1) + algorithm(1) + local_if_id(4) + local_ipv6(16) + remote_if_id(4) + remote_ipv6(16)
    )
    VALUE_WITH_SID_SIZE: ClassVar[int] = 58  # base + sid(16)
    VALUE_WITH_EB_SIZE: ClassVar[int] = 66  # base + sid(16) + endpoint_behavior(8)

    def __init__(
        self,
        local_if_id: int,
        local_ipv6: str,
        remote_if_id: int,
        remote_ipv6: str,
        algorithm: int = 0,
        flags: int = 0,
        sid: str | None = None,
        endpoint_behavior: SRv6EndpointBehavior | None = None,
    ) -> None:
        """
        Args:
            local_if_id: Local interface identifier (4 octets)
            local_ipv6: Local IPv6 node address
            remote_if_id: Remote interface identifier (4 octets, may be 0)
            remote_ipv6: Remote IPv6 node address (may be ::0)
            algorithm: SR Algorithm (valid when A-Flag is set)
            flags: Segment flags (A-Flag = 0x40, B-Flag = 0x10 for endpoint behavior)
            sid: Optional SRv6 SID (IPv6 address, can be ::0)
            endpoint_behavior: Optional SRv6 Endpoint Behavior (only if sid is present)
        """
        self.local_if_id = local_if_id
        self.local_ipv6 = local_ipv6
        self.remote_if_id = remote_if_id
        self.remote_ipv6 = remote_ipv6
        self.algorithm = algorithm
        self.flags = flags
        self.sid = sid
        self.endpoint_behavior = endpoint_behavior

    def pack(self, is_last: bool = False) -> bytes:
        """Pack the segment.

        Args:
            is_last: Unused for Type J (SRv6 has no bottom-of-stack bit).
                     Included for API consistency.
        """
        local_ipv6_bytes = socket.inet_pton(socket.AF_INET6, self.local_ipv6)
        remote_ipv6_bytes = socket.inet_pton(socket.AF_INET6, self.remote_ipv6)

        effective_flags = self.flags
        if self.endpoint_behavior is not None:
            effective_flags |= _SEG_B_FLAG_B  # Set B-Flag

        value = pack('!BB', effective_flags, self.algorithm)
        value += pack('!I', self.local_if_id)
        value += local_ipv6_bytes
        value += pack('!I', self.remote_if_id)
        value += remote_ipv6_bytes

        if self.sid is not None:
            sid_bytes = socket.inet_pton(socket.AF_INET6, self.sid)
            value += sid_bytes

            # Endpoint Behavior can only be present if SID is present
            if self.endpoint_behavior is not None:
                value += self.endpoint_behavior.pack()

        return pack('!BB', self.SUBTYPE, len(value)) + value

    def json(self) -> str:
        parts = [
            '"type": "J"',
            f'"local_if_id": {self.local_if_id}',
            f'"local_ipv6": "{self.local_ipv6}"',
            f'"remote_if_id": {self.remote_if_id}',
            f'"remote_ipv6": "{self.remote_ipv6}"',
            f'"algorithm": {self.algorithm}',
        ]
        if self.sid is not None:
            parts.append(f'"sid": "{self.sid}"')
        if self.endpoint_behavior is not None:
            parts.append(self.endpoint_behavior.json())
        return '{' + ', '.join(parts) + '}'

    @classmethod
    def unpack(cls, data: Buffer) -> SegmentTypeJ:
        if len(data) < cls.VALUE_BASE_SIZE:
            return cls(0, '::', 0, '::')

        flags = data[0]
        algorithm = data[1]
        local_if_id = unpack('!I', data[2:6])[0]
        local_ipv6 = socket.inet_ntop(socket.AF_INET6, bytes(data[6:22]))
        remote_if_id = unpack('!I', data[22:26])[0]
        remote_ipv6 = socket.inet_ntop(socket.AF_INET6, bytes(data[26:42]))

        sid = None
        endpoint_behavior: SRv6EndpointBehavior | None = None

        # Check if SRv6 SID is present (length >= 58)
        if len(data) >= cls.VALUE_WITH_SID_SIZE:
            sid = socket.inet_ntop(socket.AF_INET6, bytes(data[42:58]))

            # Check if Endpoint Behavior is present (length >= 66 and B-Flag set)
            if len(data) >= cls.VALUE_WITH_EB_SIZE and (flags & _SEG_B_FLAG_B):
                endpoint_behavior = SRv6EndpointBehavior.unpack(data[58:66])

        return cls(
            local_if_id=local_if_id,
            local_ipv6=local_ipv6,
            remote_if_id=remote_if_id,
            remote_ipv6=remote_ipv6,
            algorithm=algorithm,
            flags=flags,
            sid=sid,
            endpoint_behavior=endpoint_behavior,
        )


class SegmentTypeK:
    """Segment Type K: IPv6 Adjacency + SR Algorithm + optional SRv6 SID + Endpoint Behavior (sub-sub-TLV type 16).

    RFC 9831 Section 2.9:
    Value format:
      - Flags (1 octet)
      - SR Algorithm (1 octet) - valid when A-Flag is set
      - Local IPv6 Address (16 octets)
      - Remote IPv6 Address (16 octets)
      - SRv6 SID (optional, 16 octets)
      - SRv6 Endpoint Behavior (optional, 8 octets) - only when SID is present

    Length:
      - 34 octets when SRv6 SID is absent
      - 50 octets when SRv6 SID is present (without Endpoint Behavior)
      - 58 octets when both SRv6 SID and Endpoint Behavior are present
    """

    SUBTYPE: ClassVar[int] = 16
    VALUE_BASE_SIZE: ClassVar[int] = 34  # flags(1) + algorithm(1) + local_ipv6(16) + remote_ipv6(16)
    VALUE_WITH_SID_SIZE: ClassVar[int] = 50  # base + sid(16)
    VALUE_WITH_EB_SIZE: ClassVar[int] = 58  # base + sid(16) + endpoint_behavior(8)

    def __init__(
        self,
        local_ipv6: str,
        remote_ipv6: str,
        algorithm: int = 0,
        flags: int = 0,
        sid: str | None = None,
        endpoint_behavior: SRv6EndpointBehavior | None = None,
    ) -> None:
        """
        Args:
            local_ipv6: Local IPv6 address of the adjacency
            remote_ipv6: Remote IPv6 address of the adjacency
            algorithm: SR Algorithm (valid when A-Flag is set)
            flags: Segment flags (A-Flag = 0x40, B-Flag = 0x10 for endpoint behavior)
            sid: Optional SRv6 SID (IPv6 address, can be ::0)
            endpoint_behavior: Optional SRv6 Endpoint Behavior (only if sid is present)
        """
        self.local_ipv6 = local_ipv6
        self.remote_ipv6 = remote_ipv6
        self.algorithm = algorithm
        self.flags = flags
        self.sid = sid
        self.endpoint_behavior = endpoint_behavior

    def pack(self, is_last: bool = False) -> bytes:
        """Pack the segment.

        Args:
            is_last: Unused for Type K (SRv6 has no bottom-of-stack bit).
                     Included for API consistency.
        """
        local_bytes = socket.inet_pton(socket.AF_INET6, self.local_ipv6)
        remote_bytes = socket.inet_pton(socket.AF_INET6, self.remote_ipv6)

        effective_flags = self.flags
        if self.endpoint_behavior is not None:
            effective_flags |= _SEG_B_FLAG_B  # Set B-Flag

        value = pack('!BB', effective_flags, self.algorithm) + local_bytes + remote_bytes

        if self.sid is not None:
            sid_bytes = socket.inet_pton(socket.AF_INET6, self.sid)
            value += sid_bytes

            # Endpoint Behavior can only be present if SID is present
            if self.endpoint_behavior is not None:
                value += self.endpoint_behavior.pack()

        return pack('!BB', self.SUBTYPE, len(value)) + value

    def json(self) -> str:
        parts = [
            '"type": "K"',
            f'"local_ipv6": "{self.local_ipv6}"',
            f'"remote_ipv6": "{self.remote_ipv6}"',
            f'"algorithm": {self.algorithm}',
        ]
        if self.sid is not None:
            parts.append(f'"sid": "{self.sid}"')
        if self.endpoint_behavior is not None:
            parts.append(self.endpoint_behavior.json())
        return '{' + ', '.join(parts) + '}'

    @classmethod
    def unpack(cls, data: Buffer) -> SegmentTypeK:
        if len(data) < cls.VALUE_BASE_SIZE:
            return cls('::', '::')

        flags = data[0]
        algorithm = data[1]
        local_ipv6 = socket.inet_ntop(socket.AF_INET6, bytes(data[2:18]))
        remote_ipv6 = socket.inet_ntop(socket.AF_INET6, bytes(data[18:34]))

        sid = None
        endpoint_behavior: SRv6EndpointBehavior | None = None

        # Check if SRv6 SID is present (length >= 50)
        if len(data) >= cls.VALUE_WITH_SID_SIZE:
            sid = socket.inet_ntop(socket.AF_INET6, bytes(data[34:50]))

            # Check if Endpoint Behavior is present (length >= 58 and B-Flag set)
            if len(data) >= cls.VALUE_WITH_EB_SIZE and (flags & _SEG_B_FLAG_B):
                endpoint_behavior = SRv6EndpointBehavior.unpack(data[50:58])

        return cls(
            local_ipv6=local_ipv6,
            remote_ipv6=remote_ipv6,
            algorithm=algorithm,
            flags=flags,
            sid=sid,
            endpoint_behavior=endpoint_behavior,
        )


def _unpack_segment_subsubtlvs(
    data: Buffer,
) -> tuple[
    WeightSubSubTLV | None,
    list[
        SegmentTypeA
        | SegmentTypeB
        | SegmentTypeC
        | SegmentTypeD
        | SegmentTypeE
        | SegmentTypeF
        | SegmentTypeG
        | SegmentTypeH
        | SegmentTypeI
        | SegmentTypeJ
        | SegmentTypeK
    ],
]:
    """Parse segment list body: weight + segments."""
    weight: WeightSubSubTLV | None = None
    segments: list[
        SegmentTypeA
        | SegmentTypeB
        | SegmentTypeC
        | SegmentTypeD
        | SegmentTypeE
        | SegmentTypeF
        | SegmentTypeG
        | SegmentTypeH
        | SegmentTypeI
        | SegmentTypeJ
        | SegmentTypeK
    ] = []

    while data:
        if len(data) < 2:
            raise Notify(3, 1, f'Segment List sub-sub-TLV header truncated: got {len(data)}')
        sub_type = data[0]
        sub_len = data[1]
        header_size = 2
        if len(data) < header_size + sub_len:
            raise Notify(3, 1, f'Segment List sub-sub-TLV truncated: need {header_size + sub_len}, got {len(data)}')
        value = data[header_size : header_size + sub_len]
        if sub_type == WeightSubSubTLV.SUBTYPE:
            weight = WeightSubSubTLV.unpack(value)
        elif sub_type == SegmentTypeA.SUBTYPE:
            segments.append(SegmentTypeA.unpack(value))
        elif sub_type == SegmentTypeC.SUBTYPE:
            segments.append(SegmentTypeC.unpack(value))
        elif sub_type == SegmentTypeD.SUBTYPE:
            segments.append(SegmentTypeD.unpack(value))
        elif sub_type == SegmentTypeE.SUBTYPE:
            segments.append(SegmentTypeE.unpack(value))
        elif sub_type == SegmentTypeF.SUBTYPE:
            segments.append(SegmentTypeF.unpack(value))
        elif sub_type == SegmentTypeG.SUBTYPE:
            segments.append(SegmentTypeG.unpack(value))
        elif sub_type == SegmentTypeH.SUBTYPE:
            segments.append(SegmentTypeH.unpack(value))
        elif sub_type == SegmentTypeB.SUBTYPE:
            segments.append(SegmentTypeB.unpack(value))
        elif sub_type == SegmentTypeI.SUBTYPE:
            segments.append(SegmentTypeI.unpack(value))
        elif sub_type == SegmentTypeJ.SUBTYPE:
            segments.append(SegmentTypeJ.unpack(value))
        elif sub_type == SegmentTypeK.SUBTYPE:
            segments.append(SegmentTypeK.unpack(value))
        data = data[header_size + sub_len :]

    return weight, segments


@SubTLV.register(128)
class SegmentListSubTLV(SubTLV):
    """SR Policy Segment List Sub-TLV (type 128).

    RFC 9830 Section 2.4.4:
    Wire format: Type(1) + Length(2) + Reserved(1) + sub-sub-TLVs...
    Contains Weight sub-sub-TLV and one or more Segment sub-sub-TLVs.
    """

    SUBTYPE: ClassVar[int] = 128

    def __init__(
        self,
        weight: WeightSubSubTLV,
        segments: list[
            SegmentTypeA
            | SegmentTypeB
            | SegmentTypeC
            | SegmentTypeD
            | SegmentTypeE
            | SegmentTypeF
            | SegmentTypeG
            | SegmentTypeH
            | SegmentTypeI
            | SegmentTypeJ
            | SegmentTypeK
        ],
    ) -> None:
        self.weight = weight
        self.segments = segments

    def pack_value(self) -> bytes:
        """Pack per RFC 9830: Reserved(1) + sub-sub-TLVs.

        RFC 3032: The S-bit (bottom-of-stack) MUST be set to 1 only on the last
        MPLS label in the stack. For Type A and Type C segments with SID, we set
        is_last=True only for the last such segment in the list.
        """
        data = b'\x00'  # Reserved byte
        data += self.weight.pack()

        # Find the index of the last segment with MPLS label (Type A or Type C with SID)
        last_mpls_idx = -1
        for i in range(len(self.segments) - 1, -1, -1):
            if isinstance(self.segments[i], SegmentTypeA):
                last_mpls_idx = i
                break
            elif isinstance(self.segments[i], SegmentTypeC) and self.segments[i].sid is not None:
                last_mpls_idx = i
                break

        # Pack each segment, setting S-bit only on the last MPLS segment
        for i, seg in enumerate(self.segments):
            is_last = False
            if isinstance(seg, SegmentTypeA) or (isinstance(seg, SegmentTypeC) and seg.sid is not None):
                is_last = i == last_mpls_idx
            data += seg.pack(is_last=is_last)

        return data

    def json(self) -> str:
        segs_json = ', '.join(seg.json() for seg in self.segments)
        return f'{{"weight": {self.weight.weight}, "segments": [{segs_json}]}}'

    def __str__(self) -> str:
        parts = []
        for s in self.segments:
            if isinstance(s, SegmentTypeA):
                parts.append(str(s.label))
            elif isinstance(s, SegmentTypeB):
                parts.append(str(s.sid))
            elif isinstance(s, SegmentTypeC):
                parts.append(s.ipv4_node)
            elif isinstance(s, SegmentTypeD):
                parts.append(s.ipv6_node)
            elif isinstance(s, SegmentTypeE):
                parts.append(f'if{s.local_if_id}:{s.ipv4_node}')
            elif isinstance(s, SegmentTypeF):
                parts.append(f'{s.local_ipv4}->{s.remote_ipv4}')
            elif isinstance(s, SegmentTypeG):
                parts.append(f'if{s.local_if_id}:{s.local_ipv6}->if{s.remote_if_id}:{s.remote_ipv6}')
            elif isinstance(s, SegmentTypeH):
                parts.append(f'{s.local_ipv6}->{s.remote_ipv6}')
            elif isinstance(s, SegmentTypeI):
                parts.append(s.ipv6_node)
            elif isinstance(s, SegmentTypeJ):
                parts.append(f'if{s.local_if_id}:{s.local_ipv6}->if{s.remote_if_id}:{s.remote_ipv6}')
            elif isinstance(s, SegmentTypeK):
                parts.append(f'{s.local_ipv6}->{s.remote_ipv6}')
        segs = ' '.join(parts)
        return f'segment-list weight {self.weight.weight} [{segs}]'

    @classmethod
    def unpack(cls, data: Buffer) -> SegmentListSubTLV:
        """Unpack per RFC 9830: skip Reserved(1) byte then parse sub-sub-TLVs."""
        if len(data) < 1:
            return cls(weight=WeightSubSubTLV(1), segments=[])
        # Skip Reserved byte
        weight, segments = _unpack_segment_subsubtlvs(data[1:])
        if weight is None:
            weight = WeightSubSubTLV(1)
        return cls(weight=weight, segments=segments)
