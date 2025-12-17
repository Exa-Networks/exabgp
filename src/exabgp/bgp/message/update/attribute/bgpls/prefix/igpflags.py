"""igpflags.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.util.types import Buffer

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |D|N|L|P| Resvd.|
#     +-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.3.1
#
#           +----------+---------------------------+-----------+
#           |   Bit    | Description               | Reference |
#           +----------+---------------------------+-----------+
#           |   'D'    | IS-IS Up/Down Bit         | [RFC5305] |
#           |   'N'    | OSPF "no unicast" Bit     | [RFC5340] |
#           |   'L'    | OSPF "local address" Bit  | [RFC5340] |
#           |   'P'    | OSPF "propagate NSSA" Bit | [RFC5340] |
#           | Reserved | Reserved for future use.  |           |
#           +----------+---------------------------+-----------+

# 	RFC 7752 3.3.3.1. IGP Flags TLV


@LinkState.register_lsid(tlv=1152, json_key='igp-flags', repr_name='IGP flags')
class IgpFlags(FlagLS):
    FLAGS = ['D', 'N', 'L', 'P', 'RSV', 'RSV', 'RSV', 'RSV']
    LEN = 1

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> IgpFlags:
        cls.check(data)
        return cls(data)

    @classmethod
    def make_igp_flags(cls, flags: dict[str, int]) -> IgpFlags:
        """Create IgpFlags from flags dict.

        Args:
            flags: Dict with keys D, N, L, P (RSV bits ignored)

        Returns:
            IgpFlags instance with packed wire-format bytes
        """
        # Pack flags byte: D(7), N(6), L(5), P(4), RSV(3-0)
        flags_byte = (
            (flags.get('D', 0) << 7) | (flags.get('N', 0) << 6) | (flags.get('L', 0) << 5) | (flags.get('P', 0) << 4)
        )
        return cls(bytes([flags_byte]))
