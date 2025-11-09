
"""srv6endx.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json

from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

#    RFC 9514:  3.1.  SRv6 Capabilities TLV
#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |               Type            |          Length               |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |             Flags             |         Reserved              |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                    Figure 1: SRv6 Capabilities TLV Format


@LinkState.register()
class Srv6Capabilities(BaseLS):
    TLV = 1038
    registered_subsubtlvs = dict()

    def __init__(self, flags):
        self.flags = flags

    def __repr__(self):
        return 'flags: %s' % (self.flags)

    @classmethod
    def register(cls):
        def register_subsubtlv(klass):
            code = klass.TLV
            if code in cls.registered_subsubtlvs:
                raise RuntimeError('only one class can be registered per SRv6 Capabilities Sub-TLV type')
            cls.registered_subsubtlvs[code] = klass
            return klass

        return register_subsubtlv

    @classmethod
    def unpack(cls, data):
        flags_value = int.from_bytes(data[0:2], byteorder='big')
        flags = {'O': flags_value & (1 << 6)}
        return cls(flags=flags)

    def json(self, compact=None):
        return '"srv6-capabilities": ' + json.dumps(
            {
                'flags': self.flags,
            },
            indent=compact,
        )
