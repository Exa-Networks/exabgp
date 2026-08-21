"""isisarea.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json

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


@LinkState.register_lsid(tlv=1027, json_key='area-ids', repr_name='ISIS area ids')
class IsisArea(BaseLS):
    # RFC 9552 5.3.1.2: a node may belong to several areas, so the TLV may be present
    # more than once.  Rendered under one key it emitted that key twice and json.loads
    # kept the last, so every area but one was lost with nothing to say so
    MERGE = True

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
    def content(self) -> str:
        """The area identifier, as the decimal string the API has always carried.

        json() rendered the integer inside quotes while content returned the integer
        itself, so the two paths disagreed on the type.  The merge renders content, so the
        disagreement would have changed a string into a number for every consumer.  It is
        an identifier rather than a quantity, and nothing does arithmetic on it.
        """
        return str(int(self._packed.hex(), 16))

    def json(self, compact: bool = False) -> str:
        return f'"{self.JSON}": {json.dumps([self.content])}'
