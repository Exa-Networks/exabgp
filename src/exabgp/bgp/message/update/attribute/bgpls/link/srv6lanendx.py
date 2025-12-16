"""srv6lanendx.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import pack, unpack
from exabgp.protocol.iso import ISO
from exabgp.util import hexstring

from typing import Callable

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.protocol.ip import IP, IPv6
from exabgp.util.types import Buffer

# BGP-LS Sub-TLV header constants
BGPLS_SUBTLV_HEADER_SIZE = 4  # Sub-TLV header is 4 bytes (Type 2 + Length 2)

# Minimum data length for SRv6 LAN End.X SID TLV (RFC 9514 Section 4.2)
# ISIS: Endpoint Behavior (2) + Flags (1) + Algorithm (1) + Weight (1) + Reserved (1) + SystemID (6) + SID (16) = 28 bytes
# OSPF: Endpoint Behavior (2) + Flags (1) + Algorithm (1) + Weight (1) + Reserved (1) + RouterID (4) + SID (16) = 26 bytes
SRV6_LAN_ENDX_ISIS_MIN_LENGTH = 28
SRV6_LAN_ENDX_OSPF_MIN_LENGTH = 26

#    RFC 9514:   4.2. SRv6 LAN End.X SID TLV
#  0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |               Type            |          Length               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |       Endpoint Behavior       |      Flags    |   Algorithm   |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |     Weight    |   Reserved    |   Neighbor ID -               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+                               |
# | IS-IS System-ID (6 octets) or OSPFv3 Router-ID (4 octets)     |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (16 octets) ...                                        |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)                                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)                                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)                                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | Sub-TLVs (variable) . . .
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

# Figure 3: SRv6 LAN End.X SID TLV Format

ISIS = 1
OSPF = 2


class Srv6(FlagLS):
    @classmethod
    def _unpack_data(cls, data: Buffer, protocol_type: int) -> dict[str, object]:
        min_length = SRV6_LAN_ENDX_ISIS_MIN_LENGTH if protocol_type == ISIS else SRV6_LAN_ENDX_OSPF_MIN_LENGTH
        if len(data) < min_length:
            proto_name = 'ISIS' if protocol_type == ISIS else 'OSPF'
            raise Notify(
                3, 5, f'SRv6 LAN End.X SID ({proto_name}): data too short, need {min_length} bytes, got {len(data)}'
            )
        behavior = unpack('!I', bytes([0, 0]) + data[:2])[0]
        flags = cls.unpack_flags(data[2:3])
        algorithm = data[3]
        weight = data[4]
        if protocol_type == ISIS:
            neighbor_id = ISO.unpack_sysid(data[6:12])
        else:
            neighbor_id = str(IP.create_ip(data[6:10]))
        start_offset = 12 if protocol_type == ISIS else 6
        sid = IPv6.ntop(data[start_offset : start_offset + 16])
        data = data[start_offset + 16 :]
        subtlvs = []

        while data and len(data) >= BGPLS_SUBTLV_HEADER_SIZE:
            code = unpack('!H', data[0:2])[0]
            length = unpack('!H', data[2:4])[0]

            if code in cls.registered_subsubtlvs:
                subsubtlv = cls.registered_subsubtlvs[code].unpack_bgpls(
                    data[BGPLS_SUBTLV_HEADER_SIZE : length + BGPLS_SUBTLV_HEADER_SIZE]
                )
                subtlvs.append(subsubtlv.json())
            else:
                subsubtlv = hexstring(data[BGPLS_SUBTLV_HEADER_SIZE : length + BGPLS_SUBTLV_HEADER_SIZE])
                subtlvs.append(f'"{code}-undecoded": "{subsubtlv}"')
            data = data[length + BGPLS_SUBTLV_HEADER_SIZE :]

        return {
            'flags': flags,
            'neighbor-id': neighbor_id,
            'behavior': behavior,
            'algorithm': algorithm,
            'weight': weight,
            'sid': sid,
            **json.loads('{' + ', '.join(subtlvs) + '}'),
        }


@LinkState.register_lsid()
class Srv6LanEndXISIS(Srv6):
    TLV = 1107
    FLAGS = ['B', 'S', 'P', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    JSON = 'srv6-lan-endx-isis'
    MERGE = True  # LinkState.json() will group into array
    registered_subsubtlvs: dict[int, type] = dict()

    def __init__(self, packed: Buffer) -> None:
        """Initialize with packed bytes."""
        self._packed = packed

    @property
    def content(self) -> dict[str, object]:
        """Parse and return content from packed bytes on demand."""
        return self._unpack_data(self._packed, ISIS)

    def __repr__(self) -> str:
        d = self.content
        return 'behavior: {}, neighbor-id: {}, flags: {}, algorithm: {}, weight: {}, sid: {}'.format(
            d.get('behavior'),
            d.get('neighbor-id'),
            d.get('flags'),
            d.get('algorithm'),
            d.get('weight'),
            d.get('sid'),
        )

    @classmethod
    def register_subsubtlv(cls) -> Callable[[type], type]:
        """Register a sub-sub-TLV class for SRv6 LAN End.X ISIS."""

        def decorator(klass: type) -> type:
            code = klass.TLV
            if code in cls.registered_subsubtlvs:
                raise RuntimeError('only one class can be registered per SRv6 LAN End.X Sub-TLV type')
            cls.registered_subsubtlvs[code] = klass
            return klass

        return decorator

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> Srv6LanEndXISIS:
        return cls(data)

    @classmethod
    def make_srv6_lan_endx_isis(
        cls,
        behavior: int,
        flags: dict[str, int],
        algorithm: int,
        weight: int,
        neighbor_id: str,
        sid: str,
    ) -> Srv6LanEndXISIS:
        """Create Srv6LanEndXISIS from semantic values.

        Args:
            behavior: Endpoint behavior code
            flags: Dict with keys B, S, P
            algorithm: Algorithm value
            weight: Weight value
            neighbor_id: ISIS System ID (e.g., '0102.0304.0506')
            sid: SRv6 SID as IPv6 string (e.g., 'fc00::2')

        Returns:
            Srv6LanEndXISIS instance with packed wire-format bytes
        """
        # Pack behavior (2 bytes)
        packed = pack('!H', behavior)

        # Pack flags byte: B(7), S(6), P(5), RSV(4-0)
        flags_byte = (flags.get('B', 0) << 7) | (flags.get('S', 0) << 6) | (flags.get('P', 0) << 5)
        packed += bytes([flags_byte])

        # Pack algorithm, weight, reserved
        packed += bytes([algorithm, weight, 0])

        # Pack ISIS System ID (6 bytes) - format: XXXX.XXXX.XXXX
        sysid_parts = neighbor_id.replace('.', '')
        packed += bytes.fromhex(sysid_parts)

        # Pack SID (16 bytes IPv6)
        packed += IPv6.pton(sid)

        return cls(packed)

    def json(self, compact: bool = False) -> str:
        return '"srv6-lan-endx-isis": {}'.format(json.dumps(self.content))


@LinkState.register_lsid()
class Srv6LanEndXOSPF(Srv6):
    TLV = 1108
    FLAGS = ['B', 'S', 'P', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    JSON = 'srv6-lan-endx-ospf'
    MERGE = True  # LinkState.json() groups into array
    registered_subsubtlvs: dict[int, type] = dict()

    def __init__(self, packed: Buffer) -> None:
        """Initialize with packed bytes."""
        self._packed = packed

    @property
    def content(self) -> dict[str, object]:
        """Parse and return content from packed bytes on demand."""
        return self._unpack_data(self._packed, OSPF)

    def __repr__(self) -> str:
        d = self.content
        return 'behavior: {}, neighbor-id: {}, flags: {}, algorithm: {}, weight: {}, sid: {}'.format(
            d.get('behavior'),
            d.get('neighbor-id'),
            d.get('flags'),
            d.get('algorithm'),
            d.get('weight'),
            d.get('sid'),
        )

    @classmethod
    def register_subsubtlv(cls) -> Callable[[type], type]:
        """Register a sub-sub-TLV class for SRv6 LAN End.X OSPF."""

        def decorator(klass: type) -> type:
            code = klass.TLV
            if code in cls.registered_subsubtlvs:
                raise RuntimeError('only one class can be registered per SRv6 LAN End.X Sub-TLV type')
            cls.registered_subsubtlvs[code] = klass
            return klass

        return decorator

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> Srv6LanEndXOSPF:
        return cls(data)

    @classmethod
    def make_srv6_lan_endx_ospf(
        cls,
        behavior: int,
        flags: dict[str, int],
        algorithm: int,
        weight: int,
        neighbor_id: str,
        sid: str,
    ) -> Srv6LanEndXOSPF:
        """Create Srv6LanEndXOSPF from semantic values.

        Args:
            behavior: Endpoint behavior code
            flags: Dict with keys B, S, P
            algorithm: Algorithm value
            weight: Weight value
            neighbor_id: OSPF Router ID as IPv4 string (e.g., '192.0.2.1')
            sid: SRv6 SID as IPv6 string (e.g., 'fc00::3')

        Returns:
            Srv6LanEndXOSPF instance with packed wire-format bytes
        """
        # Pack behavior (2 bytes)
        packed = pack('!H', behavior)

        # Pack flags byte: B(7), S(6), P(5), RSV(4-0)
        flags_byte = (flags.get('B', 0) << 7) | (flags.get('S', 0) << 6) | (flags.get('P', 0) << 5)
        packed += bytes([flags_byte])

        # Pack algorithm, weight, reserved
        packed += bytes([algorithm, weight, 0])

        # Pack OSPF Router ID (4 bytes IPv4)
        packed += IP.pton(neighbor_id)

        # Pack SID (16 bytes IPv6)
        packed += IPv6.pton(sid)

        return cls(packed)

    def json(self, compact: bool = False) -> str:
        return '"srv6-lan-endx-ospf": {}'.format(json.dumps(self.content))
