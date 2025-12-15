"""igpextags.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack

from exabgp.util import split

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.util.types import Buffer

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                Extended Route Tag (one or more)             //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.3.3


@LinkState.register_lsid()
class IgpExTags(BaseLS):
    TLV = 1154
    REPR = 'IGP Extended Route Tags'
    JSON = 'igp-extended-route-tags'
    # Variable length: each extended tag is 8 bytes, length should be multiple of 8.

    @property
    def content(self) -> list[int]:
        """Unpack and return list of 64-bit extended route tags from packed bytes."""
        return [unpack('!Q', chunk)[0] for chunk in split(self._packed, 8)]

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> IgpExTags:
        cls.check(data)
        return cls(data)

    @classmethod
    def make_igp_ex_tags(cls, tags: list[int]) -> IgpExTags:
        """Create IgpExTags from list of 64-bit extended route tag values."""
        packed = b''.join(pack('!Q', tag) for tag in tags)
        return cls(packed)
