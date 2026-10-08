"""srigpprefixattr.py

Created by Evelio Vila
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from typing import ClassVar

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.util import hexstring
from exabgp.util.intvalue import json_number
from exabgp.util.types import Buffer

#    draft-gredler-idr-bgp-ls-segment-routing-ext-03
#    0                   1                   2                   3
#    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |            Type               |            Length             |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   //                       Flags (variable)                      //
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

# 	RFC 7794 IPv4/IPv6 Extended Reachability Attribute Flags


class PrefixAttributesFlags(FlagLS):
    FLAGS: ClassVar = ['X', 'R', 'N', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    # RFC 9085 2.3.2: "Length:  Variable."  This was a fixed length of one octet, so a
    # longer Flags field was a wrong size and RFC 9552 8.2.2 discarded the attribute with
    # every TLV in it.  The flags known are in the first octet, the rest is kept as sent.
    LEN: ClassVar[int] = 0

    @property
    def content(self) -> dict[str, object]:
        """The flags of the first octet, and any octet after it in hex, as json() renders them."""
        rendered: dict[str, object] = dict(self.flags)
        if len(self._packed) > 1:
            rendered['undecoded-flags'] = hexstring(self._packed[1:])
        return rendered

    def json(self, compact: bool = False) -> str:
        return f'"{self.JSON}": {json.dumps(self.content, default=json_number)}'

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> PrefixAttributesFlags:
        if not data:
            raise Notify(3, 5, 'Prefix Attribute Flags TLV is empty, it carries one octet of flags at least')
        return cls(data)

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


LinkState.register_lsid(tlv=1170, json_key='sr-prefix-attribute-flags', repr_name='Prefix Attr Flags')(
    PrefixAttributesFlags
)
