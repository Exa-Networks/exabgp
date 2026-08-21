"""opaque.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.util.types import Buffer

#
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //              Opaque Prefix Attributes  (variable)           //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.3.6
#


@LinkState.register_lsid(tlv=1157, json_key='opaque-prefix', repr_name='Opaque Prefix Attribute')
class PrefixOpaque(BaseLS):
    @property
    def content(self) -> str:
        """The opaque payload as hex.

        RFC 9552 5.3.3.6 makes this an envelope carrying IGP TLVs which this decoder does
        not look into, so the payload is arbitrary binary.  Inheriting BaseLS.content gave
        the raw bytes to jsonable(), which decodes with 'replace', so any byte which is not
        valid UTF-8 reached the API as U+FFFD and what the peer sent could not be recovered
        from what we published.

        Hex is lossless and is already what TLV 1025 renders.
        """
        return bytes(self._packed).hex()

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> PrefixOpaque:
        return cls(data)
