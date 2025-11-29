"""srv6lanendx.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import unpack
from exabgp.protocol.iso import ISO
from exabgp.util import hexstring

from typing import Callable

from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.protocol.ip import IP, IPv6

# BGP-LS Sub-TLV header constants
BGPLS_SUBTLV_HEADER_SIZE = 4  # Sub-TLV header is 4 bytes (Type 2 + Length 2)

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
    def _unpack_data(cls, data: bytes, protocol_type: int) -> dict[str, object]:
        behavior = unpack('!I', bytes([0, 0]) + data[:2])[0]
        flags = cls.unpack_flags(data[2:3])
        algorithm = data[3]
        weight = data[4]
        if protocol_type == ISIS:
            neighbor_id = ISO.unpack_sysid(data[6:12])
        else:
            neighbor_id = str(IP.unpack_ip(data[6:10]))
        start_offset = 12 if protocol_type == ISIS else 6
        sid = IPv6.ntop(data[start_offset : start_offset + 16])
        data = data[start_offset + 16 :]
        subtlvs = []

        while data and len(data) >= BGPLS_SUBTLV_HEADER_SIZE:
            code = unpack('!H', data[0:2])[0]
            length = unpack('!H', data[2:4])[0]

            if code in cls.registered_subsubtlvs:  # type: ignore[attr-defined]
                subsubtlv = cls.registered_subsubtlvs[  # type: ignore[attr-defined]
                    code
                ].unpack_bgpls(data[BGPLS_SUBTLV_HEADER_SIZE : length + BGPLS_SUBTLV_HEADER_SIZE])
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
    MERGE = True
    FLAGS = ['B', 'S', 'P', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    registered_subsubtlvs: dict[int, type] = dict()

    def __init__(self, content: dict[str, object]) -> None:
        self.content: list[dict[str, object]] = [content]

    def __repr__(self) -> str:
        return '\n'.join(
            [
                'behavior: {}, neighbor-id: {}, flags: {}, algorithm: {}, weight: {}, sid: {}'.format(
                    d.get('behavior'),
                    d.get('neighbor-id'),
                    d.get('flags'),
                    d.get('algorithm'),
                    d.get('weight'),
                    d.get('sid'),
                )
                for d in self.content
            ],
        )

    @classmethod
    def register_subsubtlv(cls) -> Callable[[type], type]:
        """Register a sub-sub-TLV class for SRv6 LAN End.X ISIS."""

        def decorator(klass: type) -> type:
            code = klass.TLV  # type: ignore[attr-defined]
            if code in cls.registered_subsubtlvs:
                raise RuntimeError('only one class can be registered per SRv6 LAN End.X Sub-TLV type')
            cls.registered_subsubtlvs[code] = klass
            return klass

        return decorator

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> Srv6LanEndXISIS:
        return cls(cls._unpack_data(data, ISIS))

    def json(self, compact: bool = False) -> str:
        return '"srv6-lan-endx-isis": [ {} ]'.format(', '.join([json.dumps(d, indent=compact) for d in self.content]))


@LinkState.register_lsid()
class Srv6LanEndXOSPF(Srv6):
    TLV = 1108
    MERGE = True
    FLAGS = ['B', 'S', 'P', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    registered_subsubtlvs: dict[int, type] = dict()

    def __init__(self, content: dict[str, object]) -> None:
        self.content: list[dict[str, object]] = [content]

    def __repr__(self) -> str:
        return '\n'.join(
            [
                'behavior: {}, neighbor-id: {}, flags: {}, algorithm: {}, weight: {}, sid: {}'.format(
                    d.get('behavior'),
                    d.get('neighbor-id'),
                    d.get('flags'),
                    d.get('algorithm'),
                    d.get('weight'),
                    d.get('sid'),
                )
                for d in self.content
            ],
        )

    @classmethod
    def register_subsubtlv(cls) -> Callable[[type], type]:
        """Register a sub-sub-TLV class for SRv6 LAN End.X OSPF."""

        def decorator(klass: type) -> type:
            code = klass.TLV  # type: ignore[attr-defined]
            if code in cls.registered_subsubtlvs:
                raise RuntimeError('only one class can be registered per SRv6 LAN End.X Sub-TLV type')
            cls.registered_subsubtlvs[code] = klass
            return klass

        return decorator

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> Srv6LanEndXOSPF:
        return cls(cls._unpack_data(data, OSPF))

    def json(self, compact: bool = False) -> str:
        return '"srv6-lan-endx-ospf": [ {} ]'.format(', '.join([json.dumps(d, indent=compact) for d in self.content]))
