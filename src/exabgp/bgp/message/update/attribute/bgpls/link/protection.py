"""protection.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS

#       0                   1
#       0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      |Protection Cap |    Reserved   |
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      https://tools.ietf.org/html/rfc5307 Sec 1.2
#      0x01  Extra Traffic
#      0x02  Unprotected
#      0x04  Shared
#      0x08  Dedicated 1:1
#      0x10  Dedicated 1+1
#      0x20  Enhanced
#      0x40  Reserved
#      0x80  Reserved


class LinkProtectionType(FlagLS):
    # FlagLS.unpack_flags reads the octet from its most significant bit down, so the list
    # is 0x80 first and 0x01 last.  It was written in the order RFC 5307 lists the values,
    # which read every capability from the mirror of its bit.  'ExtraTrafic' keeps the
    # spelling exabgp has always published, so a consumer of the key still finds it.
    FLAGS: ClassVar = [
        'RSV',
        'RSV',
        'Enhanced',
        'Dedicated 1+1',
        'Dedicated 1:1',
        'Shared',
        'Unprotected',
        'ExtraTrafic',
    ]
    LEN: ClassVar[int] = 2


LinkState.register_lsid(tlv=1093, json_key='link-protection-flags', repr_name='Link protection mask')(
    LinkProtectionType
)
