"""opaque.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json

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


@LinkState.register_lsid(tlv=1097, json_key='opaque-link', repr_name='Opaque Link attribute')
class LinkOpaque(BaseLS):
    @property
    def content(self) -> str:
        """The opaque payload as hex.

        RFC 9552 5.3.2.6 makes this an envelope carrying IGP TLVs, and the comment above
        says it plainly: we do not look into it.  So the payload is arbitrary binary, and
        rendering it as text was a category error.  It went through jsonable(), which
        decodes with 'replace', so any byte which is not valid UTF-8 reached the API as
        U+FFFD and the value the peer sent could not be recovered from what we published.

        Hex is lossless, unambiguous, and already what TLV 1025 renders, so this also
        stops the three opaque TLVs disagreeing with each other.
        """
        return bytes(self._packed).hex()

    def json(self, compact: bool = False) -> str:
        return f'"{self.JSON}": {json.dumps(self.content)}'

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> LinkOpaque:
        return cls(data)
