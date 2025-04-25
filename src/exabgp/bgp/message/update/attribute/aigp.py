# encoding: utf-8
"""
aigp.py

Created by Thomas Mangin on 2013-09-24.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.attribute import Attribute


# ========================================================================== TLV
#

# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |     Type      |         Length                |               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+               |
# ~                                                               ~
# |                           Value                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+..........................

# Length: Two octets encoding the length in octets of the TLV,
# including the type and length fields.


class TLV(object):
    def __init__(self, what, value):
        self.type = what
        self.value = value


class TLVS(list):
    @staticmethod
    def unpack(data):
        def loop(data):
            while data:
                t = data[0]
                length = unpack('!H', data[1:3])[0]
                v, data = data[3:length], data[length:]
                yield TLV(t, v)

        return TLVS(list(loop(data)))

    def pack(self):
        return b''.join([bytes([tlv.type]) + pack('!H', len(tlv.value) + 3) + tlv.value for tlv in self])


# ==================================================================== AIGP (26)
#


@Attribute.register()
class AIGP(Attribute):
    ID = Attribute.CODE.AIGP
    FLAG = Attribute.Flag.OPTIONAL
    CACHING = True
    TYPES = [
        1,
    ]

    def __init__(self, aigp, packed=None):
        self.aigp = aigp
        if packed:
            self._packed = packed
        else:
            self._packed = self._attribute(aigp)

    def __eq__(self, other):
        return self.ID == other.ID and self.FLAG == other.FLAG and self.aigp == other.aigp

    def __ne__(self, other):
        return not self.__eq__(other)

    def pack(self, negotiated):
        if negotiated.aigp:
            return self._packed
        if negotiated.local_as == negotiated.peer_as:
            return self._packed
        return b''

    def __repr__(self):
        return '0x' + ''.join('%02x' % _ for _ in self.aigp[-8:])

    @classmethod
    def unpack(cls, data, direction, negotiated):
        if not negotiated.aigp:
            # AIGP must only be accepted on configured sessions
            return None
        return cls(unpack('!Q', data[:8] & 0x000000FFFFFFFFFF), data[:8])
