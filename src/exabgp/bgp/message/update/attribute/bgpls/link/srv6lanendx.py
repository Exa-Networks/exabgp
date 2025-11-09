
"""srv6lanendx.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import unpack
from exabgp.protocol.iso import ISO
from exabgp.util import hexstring

from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.protocol.ip import IP, IPv6

#    RFC 9514:   4.2. SRv6 LAN End.X SID TLV
#  0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |               Type            |          Length               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |       Endpoint Behavior       |      Flags    |   Algorithm   |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |     Weight    |   Reserved    |   Neighbor ID -               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+                               |
# | IS-IS System-ID (6 octets) or OSPFv3 Router-ID (4 octets)     |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (16 octets) ...                                        |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)                                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)                                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |    SID (cont ...)                                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | Sub-TLVs (variable) . . .
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

# Figure 3: SRv6 LAN End.X SID TLV Format

ISIS = 1
OSPF = 2


def unpack_data(cls, data, type):
    behavior = unpack('!I', bytes([0, 0]) + data[:2])[0]
    flags = cls.unpack_flags(data[2:3])
    algorithm = data[3]
    weight = data[4]
    if type == ISIS:
        neighbor_id = ISO.unpack_sysid(data[6:12])
    else:
        neighbor_id = IP.unpack(data[6:10])
    start_offset = 12 if type == ISIS else 6
    sid = IPv6.ntop(data[start_offset : start_offset + 16])
    data = data[start_offset + 16 :]
    subtlvs = []

    while data and len(data) >= 4:
        code = unpack('!H', data[0:2])[0]
        length = unpack('!H', data[2:4])[0]

        if code in cls.registered_subsubtlvs:
            subsubtlv = cls.registered_subsubtlvs[code].unpack(data[4 : length + 4])
            subtlvs.append(subsubtlv.json())
        else:
            subsubtlv = hexstring(data[4 : length + 4])
            subtlvs.append(f'"{code}-undecoded": "{subsubtlv}"')
        data = data[length + 4 :]

    return {
        'flags': flags,
        'neighbor-id': neighbor_id,
        'behavior': behavior,
        'algorithm': algorithm,
        'weight': weight,
        'sid': sid
    , **json.loads('{' + ', '.join(subtlvs) + '}')}


@LinkState.register()
class Srv6LanEndXISIS(FlagLS):
    TLV = 1107
    MERGE = True
    FLAGS = ['B', 'S', 'P', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    registered_subsubtlvs = dict()

    def __init__(self, content):
        self.content = [content]

    def __repr__(self):
        return '\n'.join(
            [
                'behavior: %s, neighbor-id: %s, flags: %s, algorithm: %s, weight: %s, sid: %s'
                % (d.behavior, d.neighbor_id, d.flags, d.algorithm, d.weight, d.sid)
                for d in self.content
            ],
        )

    @classmethod
    def register(cls):
        def register_subsubtlv(klass):
            code = klass.TLV
            if code in cls.registered_subsubtlvs:
                raise RuntimeError('only one class can be registered per SRv6 LAN End.X Sub-TLV type')
            cls.registered_subsubtlvs[code] = klass
            return klass

        return register_subsubtlv

    @classmethod
    def unpack(cls, data):
        return cls(unpack_data(cls, data, ISIS))

    def json(self, compact=None):
        return '"srv6-lan-endx-isis": [ %s ]' % ', '.join([json.dumps(d, indent=compact) for d in self.content])


@LinkState.register()
class Srv6LanEndXOSPF(FlagLS):
    TLV = 1108
    MERGE = True
    FLAGS = ['B', 'S', 'P', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    registered_subsubtlvs = dict()

    def __init__(self, content):
        self.content = [content]

    def __repr__(self):
        return '\n'.join(
            [
                'behavior: %s, neighbor-id: %s, flags: %s, algorithm: %s, weight: %s, sid: %s'
                % (d.behavior, d.neighbor_id, d.flags, d.algorithm, d.weight, d.sid)
                for d in self.content
            ],
        )

    @classmethod
    def register(cls):
        def register_subsubtlv(klass):
            code = klass.TLV
            if code in cls.registered_subsubtlvs:
                raise RuntimeError('only one class can be registered per SRv6 LAN End.X Sub-TLV type')
            cls.registered_subsubtlvs[code] = klass
            return klass

        return register_subsubtlv

    @classmethod
    def unpack(cls, data):
        return cls(unpack_data(cls, data, OSPF))

    def json(self, compact=None):
        return '"srv6-lan-endx-ospf": [ %s ]' % ', '.join([json.dumps(d, indent=compact) for d in self.content])
