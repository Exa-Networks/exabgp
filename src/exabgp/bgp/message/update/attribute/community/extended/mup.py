# encoding: utf-8
"""
mup.py

Created by Takeru Hayasaka on 2023-03-13.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

# draft-mpmz-bess-mup-safi-02
# 0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |     0x0c      |     0x00      |  Direct Segment Identifier    |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |              Direct Segment Identifier (cont.)                |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


@ExtendedCommunity.register
class MUPExtendedCommunity(ExtendedCommunity):
    COMMUNITY_TYPE = 0x0C
    # Direct-Type Segment Identifier type
    COMMUNITY_SUBTYPE = 0x00
    LIMIT = 4

    def __init__(self, sgid2, sgid4, transitive=True, community=None):
        self.sgid2 = sgid2
        self.sgid4 = sgid4
        ExtendedCommunity.__init__(
            self, community if community else pack('!2sHL', self._subtype(transitive), sgid2, sgid4)
        )

    def __eq__(self, other):
        return (
            self.COMMUNITY_SUBTYPE == other.COMMUNITY_SUBTYPE
            and self.COMMUNITY_TYPE == other.COMMUNITY_TYPE
            and ExtendedCommunity.__eq__(self, other)
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.sgid2, self.sgid4))

    def __repr__(self):
        return '%s:%d:%d' % ('mup', self.sgid2, self.sgid4)

    @classmethod
    def unpack(cls, data):
        sgid2, sgid4 = unpack('!HL', data[2:8])
        return MUPExtendedCommunity(sgid2, sgid4, False, data[:8])
