"""linkname.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS, LinkState
from exabgp.util.types import Buffer

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                     Link Name (variable)                    //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.2.7  Link Name TLV


@LinkState.register_lsid()
class LinkName(BaseLS):
    TLV = 1098
    REPR = 'Link Name'
    JSON = 'link-name'

    # BGP-LS TLV length constants
    BGPLS_TLV_MAX_LENGTH = 255  # Maximum TLV data length

    @property
    def content(self) -> bytes:
        """Return the raw bytes (link name is stored as bytes)."""
        return self._packed

    @classmethod
    def make_linkname(cls, name: str) -> LinkName:
        """Factory method to create LinkName from string."""
        return cls(name.encode('utf-8'))

    def json(self, compact: bool = False) -> str:
        """Return JSON representation, decoding bytes to string."""
        return f'"{self.JSON}": {json.dumps(self._packed.decode("utf-8"))}'

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> LinkName:
        if len(data) > cls.BGPLS_TLV_MAX_LENGTH:
            raise Notify(3, 5, 'Link Name TLV length too large')
        return cls(data)
