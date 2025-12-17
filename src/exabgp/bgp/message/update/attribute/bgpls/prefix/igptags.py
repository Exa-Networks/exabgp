"""igptags.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack

from exabgp.util import split

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.util.types import Buffer

#   The IGP Route Tag TLV carries original IGP Tags (IS-IS [RFC5130] or
#   OSPF) of the prefix and is encoded as follows:
#
#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                    Route Tags (one or more)                 //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.3.2


@LinkState.register_lsid(tlv=1153, json_key='igp-route-tags', repr_name='IGP Route Tags')
class IgpTags(BaseLS):
    # Variable length: each tag is 4 bytes, length should be multiple of 4.

    @property
    def content(self) -> list[int]:
        """Unpack and return list of 32-bit route tags from packed bytes."""
        return [unpack('!L', chunk)[0] for chunk in split(self._packed, 4)]

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> IgpTags:
        cls.check(data)
        return cls(data)

    @classmethod
    def make_igp_tags(cls, tags: list[int]) -> IgpTags:
        """Create IgpTags from list of 32-bit route tag values."""
        packed = b''.join(pack('!L', tag) for tag in tags)
        return cls(packed)
