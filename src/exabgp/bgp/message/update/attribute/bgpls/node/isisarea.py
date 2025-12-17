"""isisarea.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.util.types import Buffer

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                 Area Identifier (variable)                  //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.1.2


@LinkState.register_lsid(tlv=1027, json_key='area-id', repr_name='ISIS area id')
class IsisArea(BaseLS):
    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> IsisArea:
        if not data:
            raise Notify(3, 5, 'ISIS Area: empty data')
        return cls(data)

    @classmethod
    def make_isis_area(cls, areaid: int) -> IsisArea:
        """Create IsisArea from area ID integer.

        Args:
            areaid: ISIS area ID as integer

        Returns:
            IsisArea instance with packed wire-format bytes
        """
        # Convert integer to minimum bytes needed
        if areaid == 0:
            packed = b'\x00'
        else:
            hex_str = format(areaid, 'x')
            # Ensure even length for bytes.fromhex
            if len(hex_str) % 2:
                hex_str = '0' + hex_str
            packed = bytes.fromhex(hex_str)
        return cls(packed)

    @property
    def content(self) -> int:
        """ISIS area ID as integer."""
        return int(self._packed.hex(), 16)

    def json(self, compact: bool = False) -> str:
        return f'"{self.JSON}": "{self.content}"'
