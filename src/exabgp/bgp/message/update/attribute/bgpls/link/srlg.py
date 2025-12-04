"""srlg.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack
from typing import Sequence
from exabgp.util import split

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS


#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                  Shared Risk Link Group Value                 |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                         ............                        //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                  Shared Risk Link Group Value                 |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.2.5 Shared Risk Link Group TLV


@LinkState.register_lsid()
class Srlg(BaseLS):
    TLV = 1096
    REPR = 'link SRLG values'
    JSON = 'shared-risk-link-groups'

    @property
    def content(self) -> list[int]:
        """Unpack and return the SRLG values from packed bytes."""
        return [unpack('!L', chunk)[0] for chunk in split(self._packed, 4)]

    @classmethod
    def make_srlg(cls, srlg_values: Sequence[int]) -> Srlg:
        """Factory method to create Srlg from list of SRLG values."""
        packed = b''.join(pack('!I', v) for v in srlg_values)
        return cls(packed)

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> Srlg:
        if len(data) % 4:
            raise Notify(3, 5, 'Unable to decode SRLG')
        return cls(data)
