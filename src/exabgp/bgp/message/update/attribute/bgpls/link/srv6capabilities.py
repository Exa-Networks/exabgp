"""srv6capabilities.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from typing import Callable

from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.util.types import Buffer

#    RFC 9514:  3.1.  SRv6 Capabilities TLV
#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |               Type            |          Length               |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |             Flags             |         Reserved              |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                    Figure 1: SRv6 Capabilities TLV Format

# Fixed length: Flags (2) + Reserved (2) = 4 bytes
SRV6_CAPABILITIES_LEN = 4


@LinkState.register_lsid(tlv=1038, json_key='srv6-capabilities', repr_name='SRv6 Capabilities')
class Srv6Capabilities(BaseLS):
    LEN = SRV6_CAPABILITIES_LEN
    registered_subsubtlvs: dict[int, type] = dict()

    @property
    def flags(self) -> dict[str, int]:
        """Unpack and return flags from packed bytes."""
        flags_value = int.from_bytes(self._packed[0:2], byteorder='big')
        return {'O': flags_value & (1 << 6)}

    def __repr__(self) -> str:
        return 'flags: {}'.format(self.flags)

    @classmethod
    def register_subsubtlv(cls) -> Callable[[type], type]:
        """Register a sub-sub-TLV class for SRv6 Capabilities."""

        def decorator(klass: type) -> type:
            code = klass.TLV
            if code in cls.registered_subsubtlvs:
                raise RuntimeError('only one class can be registered per SRv6 Capabilities Sub-TLV type')
            cls.registered_subsubtlvs[code] = klass
            return klass

        return decorator

    @classmethod
    def make_srv6_capabilities(cls, flags: dict[str, int]) -> Srv6Capabilities:
        """Create Srv6Capabilities from semantic values.

        Args:
            flags: Dict with 'O' key (bit 6 of flags field)

        Returns:
            Srv6Capabilities instance
        """
        # Build 16-bit flags field
        flags_value = (flags.get('O', 0) & 1) << 6
        # Pack: Flags (2 bytes) + Reserved (2 bytes)
        packed = flags_value.to_bytes(2, byteorder='big') + b'\x00\x00'
        return cls(packed)

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> Srv6Capabilities:
        cls.check(data)
        return cls(data)

    def json(self, compact: bool = False) -> str:
        return '"srv6-capabilities": ' + json.dumps(
            {
                'flags': self.flags,
            },
            indent=compact,
        )
