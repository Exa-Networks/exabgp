"""opaque.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.util.types import Buffer

#
#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |              Type             |             Length            |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    //                     Opaque link attributes (variable)       //
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.2.6 Opaque Link Attribute TLV
#
# This TLV is added here for completeness but we don't look into the TLV.


@LinkState.register_lsid()
class LinkOpaque(BaseLS):
    TLV = 1097
    REPR = 'Opaque Link attribute'
    JSON = 'opaque-link'

    @property
    def content(self) -> bytes:
        """Return the raw opaque bytes."""
        return self._packed

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> LinkOpaque:
        return cls(data)
