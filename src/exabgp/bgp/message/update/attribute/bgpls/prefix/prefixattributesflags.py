"""srigpprefixattr.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS

#    draft-gredler-idr-bgp-ls-segment-routing-ext-03
#    0                   1                   2                   3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |            Type               |            Length             |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   //                       Flags (variable)                      //
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

# 	RFC 7794 IPv4/IPv6 Extended Reachability Attribute Flags


@LinkState.register_lsid(tlv=1170, json_key='sr-prefix-attribute-flags', repr_name='Prefix Attr Flags')
class PrefixAttributesFlags(FlagLS):
    FLAGS = ['X', 'R', 'N', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    LEN = 1

    @classmethod
    def make_prefix_attributes_flags(cls, flags: dict[str, int]) -> PrefixAttributesFlags:
        """Create PrefixAttributesFlags from flags dict.

        Args:
            flags: Dict with X, R, N flag values (0 or 1)

        Returns:
            PrefixAttributesFlags instance with packed wire-format bytes
        """
        flags_byte = (flags.get('X', 0) << 7) | (flags.get('R', 0) << 6) | (flags.get('N', 0) << 5)
        return cls(bytes([flags_byte]))
