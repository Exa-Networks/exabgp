# encoding: utf-8
"""
srv6endx.py

Created by Vincent Bernat
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import unpack
from exabgp.util import hexstring

from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.protocol.ip import IPv6

#    RFC 9514:  4.1. SRv6 End.X SID TLV
#  0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |               Type            |          Length               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |        Endpoint Behavior      |      Flags    |   Algorithm   |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |     Weight    |   Reserved    |  SID (16 octets) ...          |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)                                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)                                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)                                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)             | Sub-TLVs (variable) . . .
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


@LinkState.register()
class Srv6EndX(FlagLS):
    TLV = 1106
    FLAGS = ['B', 'S', 'P', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    MERGE = True
    registered_subsubtlvs = dict()

    def __init__(self, content):
        self.content = [ content ]

    def __repr__(self):
        return '\n'.join(['behavior: %s, flags: %s, algorithm: %s, sid: %s' % (d.behavior, d.flags, d.algorithm, d.sid) for d in self.content])

    @classmethod
    def register(cls):
        def register_subsubtlv(klass):
            code = klass.TLV
            if code in cls.registered_subsubtlvs:
                raise RuntimeError('only one class can be registered per SRv6 End.X Sub-TLV type')
            cls.registered_subsubtlvs[code] = klass
            return klass

        return register_subsubtlv

    @classmethod
    def unpack(cls, data):
        behavior = unpack("!I", bytes([0,0])+data[:2])[0]
        flags = cls.unpack_flags(data[2:3])
        algorithm = data[3]
        weight = data[4]
        sid = IPv6.ntop(data[6:22])
        data = data[22:]
        subtlvs = []

        while data and len(data) >= 4: 
            code = unpack('!H', data[0:2])[0]
            length = unpack('!H', data[2:4])[0]

            if code in cls.registered_subsubtlvs:
                subsubtlv = cls.registered_subsubtlvs[code].unpack(data[4:length + 4])
            else:
                subsubtlv = hexstring(data[4:length + 4])
            data = data[length + 4:]

            subtlvs.append(subsubtlv.json())

        content = { "flags": flags, "behavior": behavior, "algorithm": algorithm, "weight": weight, "sid": sid } | json.loads('{'+ ', '.join(subtlvs) + '}')

        return cls(content=content)

    def json(self, compact=None):
        return '"srv6-endx": [ %s ]' % ', '.join([json.dumps(d, indent=compact) for d in self.content])
