"""srv6endx.py

Created by Vincent Bernat
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import pack, unpack
from typing import Callable

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS, LinkState
from exabgp.protocol.ip import IPv6
from exabgp.util import hexstring
from exabgp.util.types import Buffer

# Minimum data length for SRv6 End.X SID TLV (RFC 9514 Section 4.1)
# Endpoint Behavior (2) + Flags (1) + Algorithm (1) + Weight (1) + Reserved (1) + SID (16) = 22 bytes
SRV6_ENDX_MIN_LENGTH = 22

#    RFC 9514:  4.1. SRv6 End.X SID TLV
#  0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |               Type            |          Length               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |        Endpoint Behavior      |      Flags    |   Algorithm   |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |     Weight    |   Reserved    |  SID (16 octets) ...          |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)                                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)                                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)                                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)             | Sub-TLVs (variable) . . .
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


@LinkState.register_lsid(tlv=1106, json_key='srv6-endx', repr_name='SRv6 End.X SID')
class Srv6EndX(FlagLS):
    FLAGS = ['B', 'S', 'P', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    MERGE = True  # LinkState.json() groups into array
    registered_subsubtlvs: dict[int, type] = dict()

    def __init__(self, packed: Buffer) -> None:
        """Initialize with packed bytes."""
        self._packed = packed

    @property
    def content(self) -> dict[str, object]:
        """Parse and return content from packed bytes on demand."""
        return self._unpack_data(self._packed)

    def __repr__(self) -> str:
        d = self.content
        return 'behavior: {}, flags: {}, algorithm: {}, weight: {}, sid: {}'.format(
            d.get('behavior'), d.get('flags'), d.get('algorithm'), d.get('weight'), d.get('sid')
        )

    @classmethod
    def register_subsubtlv(cls) -> Callable[[type], type]:
        """Register a sub-sub-TLV class for SRv6 End.X."""

        def decorator(klass: type) -> type:
            code = klass.TLV
            if code in cls.registered_subsubtlvs:
                raise RuntimeError('only one class can be registered per SRv6 End.X Sub-TLV type')
            cls.registered_subsubtlvs[code] = klass
            return klass

        return decorator

    @classmethod
    def _unpack_data(cls, data: Buffer) -> dict[str, object]:
        """Parse SRv6 End.X SID TLV data into dict."""
        if len(data) < SRV6_ENDX_MIN_LENGTH:
            raise Notify(3, 5, f'SRv6 End.X SID: data too short, need {SRV6_ENDX_MIN_LENGTH} bytes, got {len(data)}')
        behavior = unpack('!I', bytes([0, 0]) + data[:2])[0]
        flags = cls.unpack_flags(data[2:3])
        algorithm = data[3]
        weight = data[4]
        sid = IPv6.ntop(data[6:22])
        data = data[22:]
        subtlvs = []

        while data and len(data) >= cls.BGPLS_SUBTLV_HEADER_SIZE:
            code = unpack('!H', data[0:2])[0]
            length = unpack('!H', data[2:4])[0]

            if code in cls.registered_subsubtlvs:
                subsubtlv = cls.registered_subsubtlvs[code].unpack_bgpls(
                    data[cls.BGPLS_SUBTLV_HEADER_SIZE : length + cls.BGPLS_SUBTLV_HEADER_SIZE]
                )
                subtlvs.append(subsubtlv.json())
            else:
                # Unknown sub-TLV: format as JSON string with hex data
                hex_data = hexstring(data[cls.BGPLS_SUBTLV_HEADER_SIZE : length + cls.BGPLS_SUBTLV_HEADER_SIZE])
                subtlvs.append(f'"unknown-subtlv-{code}": "{hex_data}"')
            data = data[length + cls.BGPLS_SUBTLV_HEADER_SIZE :]

        return {
            'flags': flags,
            'behavior': behavior,
            'algorithm': algorithm,
            'weight': weight,
            'sid': sid,
            **json.loads('{' + ', '.join(subtlvs) + '}'),
        }

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> Srv6EndX:
        return cls(data)

    @classmethod
    def make_srv6_endx(
        cls,
        behavior: int,
        flags: dict[str, int],
        algorithm: int,
        weight: int,
        sid: str,
    ) -> Srv6EndX:
        """Create Srv6EndX from semantic values.

        Args:
            behavior: Endpoint behavior (16-bit)
            flags: Dict with B, S, P flag values
            algorithm: SR algorithm
            weight: Weight value
            sid: SRv6 SID as IPv6 string

        Returns:
            Srv6EndX instance with packed wire-format bytes
        """
        # Behavior (2 bytes) + Flags (1) + Algorithm (1) + Weight (1) + Reserved (1) + SID (16)
        flags_byte = (flags.get('B', 0) << 7) | (flags.get('S', 0) << 6) | (flags.get('P', 0) << 5)
        packed = pack('!HBBBx', behavior, flags_byte, algorithm, weight)
        packed += IPv6.pton(sid)
        return cls(packed)

    def json(self, compact: bool = False) -> str:
        return '"srv6-endx": {}'.format(json.dumps(self.content))
