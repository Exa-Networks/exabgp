"""srv6lanendx.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import unpack
from exabgp.protocol.iso import ISO

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState, unpack_subtlvs
from exabgp.protocol.ip import IP, IPv6

# BGP-LS Sub-TLV header constants
BGPLS_SUBTLV_HEADER_SIZE = 4  # Sub-TLV header is 4 bytes (Type 2 + Length 2)

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


# Behavior(2) + Flags(1) + Algorithm(1) + Weight(1) + Reserved(1) + Neighbor Id + SID(16)
FIXED_SIZE_ISIS = 28
# RFC 9514 4.2: behavior 2, flags 1, algorithm 1, weight 1, reserved 1, then the neighbour's
# identifier and a 16 octet SID. IS-IS names it with a 6 octet System-ID and OSPFv3 with a
# 4 octet Router-ID, so 6 + 6 + 16 and 6 + 4 + 16. This read 22, which is 6 + 16: the length
# agreed with the wrong SID offset below, so the two faults hid each other.
FIXED_SIZE_OSPF = 26


def unpack_data(cls, data, type):
    needed = FIXED_SIZE_ISIS if type == ISIS else FIXED_SIZE_OSPF
    if len(data) < needed:
        raise Notify(3, 5, f'Unable to decode attribute, not enough data for {cls.__name__}')
    behavior = unpack('!I', bytes([0, 0]) + data[:2])[0]
    flags = cls.unpack_flags(data[2:3])
    algorithm = data[3]
    weight = data[4]
    if type == ISIS:
        neighbor_id = ISO.unpack_sysid(data[6:12])
    else:
        # json.dumps cannot serialise an IP object, and this reaches it through content
        neighbor_id = str(IP.unpack(data[6:10]))
    # past the neighbour's identifier, which is 6 octets for IS-IS and 4 for OSPFv3. Reading
    # the OSPF SID from 6 is the offset of the Router-ID, not of the SID, so the Router-ID's
    # four octets were reported as the head of the SID and the SID's last four fell past the
    # end, where the sub-TLV walk below read them as a header.
    start_offset = 12 if type == ISIS else 10
    sid = IPv6.ntop(data[start_offset : start_offset + 16])
    data = data[start_offset + 16 :]
    # 'N-undecoded' is a published member name and differs from the one the non-LAN sibling
    # emits. Neither may be renamed, so each caller passes its own formatter.
    subtlvs = unpack_subtlvs(
        data,
        cls.registered_subsubtlvs,
        lambda code, value: f'"{code}-undecoded": "{value}"',
        'SRv6 LAN End.X SID',
    )

    return {
        'flags': flags,
        'neighbor-id': neighbor_id,
        'behavior': behavior,
        'algorithm': algorithm,
        'weight': weight,
        'sid': sid,
        **json.loads('{' + ', '.join(subtlvs) + '}'),
    }


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
                # content holds dicts, attribute access raised AttributeError from str()
                'behavior: {}, neighbor-id: {}, flags: {}, algorithm: {}, weight: {}, sid: {}'.format(
                    d['behavior'], d['neighbor-id'], d['flags'], d['algorithm'], d['weight'], d['sid']
                )
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
        return '"srv6-lan-endx-isis": [ {} ]'.format(', '.join([json.dumps(d, indent=compact) for d in self.content]))

    def as_dict(self):
        return {'srv6-lan-endx-isis': self.content}


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
                # content holds dicts, attribute access raised AttributeError from str()
                'behavior: {}, neighbor-id: {}, flags: {}, algorithm: {}, weight: {}, sid: {}'.format(
                    d['behavior'], d['neighbor-id'], d['flags'], d['algorithm'], d['weight'], d['sid']
                )
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
        return '"srv6-lan-endx-ospf": [ {} ]'.format(', '.join([json.dumps(d, indent=compact) for d in self.content]))

    def as_dict(self):
        return {'srv6-lan-endx-ospf': self.content}
