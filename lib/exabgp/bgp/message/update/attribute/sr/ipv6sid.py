# encoding: utf-8
"""
sr/ipv6sid.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""
from struct import pack

from exabgp.util import concat_bytes
from exabgp.protocol.ip import IP

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid

# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |       Type    |             Length            |   RESERVED    |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |            RESERVED           |                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+                               |
# |                                                               |
# |                        IPv6 SID (16 octets)                   |
# |                                                               |
# |                               +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# 3.2.  IPv6 SID


@PrefixSid.register()
class SrV6Sid(object):
    TLV = 2
    LENGTH = 19

    def __init__(self, v6sid, packed=None):
        self.v6sid = v6sid
        self.packed = self.pack()

    def __repr__(self):
        return "sr-v6-sid %s" % (self.v6sid)

    def pack(self):
        return concat_bytes(
            pack('!B', self.TLV), pack('!H', self.LENGTH), pack('!B', 0), pack('!H', 0), IP.pton(self.v6sid)
        )

    @classmethod
    def unpack(cls, data, length):
        v6sid = -1
        if cls.LENGTH != length:
            raise Notify(3, 5, "Invalid TLV size. Should be {0} but {1} received".format(cls.LENGTH, length))
        # RESERVED: 24 bit field for future use.  MUST be clear on
        # transmission an MUST be ignored at reception.
        data = data[3:19]
        v6sid = IP.unpack(data)
        return cls(v6sid=str(v6sid), packed=data)

    def json(self, compact=None):
        return '"sr-v6-sid": "%s"' % (self.v6sid)
