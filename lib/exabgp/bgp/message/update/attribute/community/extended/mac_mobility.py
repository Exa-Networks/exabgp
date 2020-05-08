# encoding: utf-8
"""
mac_mobility.py

Created by Anton Aksola on 2018-11-03
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

# ================================================================== MacMobility
# RFC 7432 Section 7.7.


@ExtendedCommunity.register
class MacMobility(ExtendedCommunity):
    COMMUNITY_TYPE = 0x06
    COMMUNITY_SUBTYPE = 0x00
    DESCRIPTION = 'mac-mobility'

    __slots__ = ['sequence', 'sticky']

    def __init__(self, sequence, sticky=False, community=None):
        self.sequence = sequence
        self.sticky = sticky
        ExtendedCommunity.__init__(
            self,
            community if community else pack('!2sBxI', self._subtype(transitive=True), 1 if sticky else 0, sequence),
        )

    def __hash__(self):
        return hash((self.sticky, self.sequence))

    def __repr__(self):
        s = "%s:%d" % (self.DESCRIPTION, self.sequence)
        if self.sticky:
            s += ":sticky"
        return s

    @staticmethod
    def unpack(data):
        flags, seq = unpack('!BxI', data[2:8])
        return MacMobility(seq, True if flags == 1 else False)
