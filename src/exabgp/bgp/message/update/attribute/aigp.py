"""aigp.py

Created by Thomas Mangin on 2013-09-24.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from struct import unpack

from exabgp.bgp.message.notification import Notify
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


class TLV:
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
        return '0x' + ''.join('{:02x}'.format(_) for _ in self.aigp[-8:])

    # AIGP TLV for the IGP metric: type(1) + length(2) + value(8)
    TLV_AIGP = 1
    TLV_LENGTH = 11

    @classmethod
    def unpack(cls, data, direction, negotiated):
        if not negotiated.aigp:
            # AIGP must only be accepted on configured sessions
            return None

        # RFC 7311 section 3: the attribute is a sequence of TLVs. Every TLV must be
        # walked, otherwise trailing bytes are silently dropped and a malformed
        # attribute is re-advertised as if it had been well formed.
        metric = None
        offset = 0
        while offset < len(data):
            if len(data) - offset < 3:
                raise Notify(3, 9, 'AIGP TLV header truncated at offset {}'.format(offset))
            tlv_type = data[offset]
            tlv_length = unpack('!H', data[offset + 1 : offset + 3])[0]
            if tlv_length < 3:
                raise Notify(3, 9, 'AIGP TLV length {} is smaller than its own header'.format(tlv_length))
            if len(data) - offset < tlv_length:
                raise Notify(
                    3,
                    9,
                    'AIGP TLV truncated: {} bytes announced, {} available'.format(tlv_length, len(data) - offset),
                )
            if tlv_type == cls.TLV_AIGP:
                if tlv_length != cls.TLV_LENGTH:
                    raise Notify(3, 9, 'Invalid AIGP TLV length: {}'.format(tlv_length))
                if metric is None:
                    metric = data[offset : offset + tlv_length]
            offset += tlv_length

        # unknown TLV types are ignored per RFC 7311, but the AIGP TLV itself is required
        if metric is None:
            raise Notify(3, 9, 'AIGP attribute has no AIGP TLV')

        return cls(metric)
