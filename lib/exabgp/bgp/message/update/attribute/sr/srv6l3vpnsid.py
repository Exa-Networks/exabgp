# encoding: utf-8
"""
sr/srv6l3vpnsid.py

Created by Hiroki Shirokura 2020-01-09
Copyright (c) 2020 Hiroki Shirokura . All rights reserved.
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
# |                                                               |
# |                      L3VPN SID (16 octets)                    |
# |                                                               |
# |                                                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | 　SID Flags   |       Endpoint Behavior       |   RESERVED    |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# 3.2.  SRv6 L3 Service


@PrefixSid.register()
class Srv6L3vpnSid(object):
    TLV = 5
    LENGTH = 21

    def __init__(self, l3vpnsid, packed=None):
        self.l3vpnsid = l3vpnsid
        self.packed = self.pack()

    def __repr__(self):
        return "srv6-l3vpn-sid %s" % (self.l3vpnsid)

    def pack(self):
        return concat_bytes(
            pack('!B', self.TLV),
            pack('!H', self.LENGTH),
            pack('!B', 0),
            IP.pton(self.l3vpnsid),
            pack('!B', 0),
            pack('!H', 0xFFFF),
            pack('!B', 0),
        )

    @classmethod
    def unpack(cls, data, length):
        l3vpnsid = -1
        if cls.LENGTH != length:
            raise Notify(3, 5, "Invalid TLV size. Should be {0} but {1} received".format(cls.LENGTH, length))
        l3vpnsid = IP.unpack(data[1:17])
        return cls(l3vpnsid=str(l3vpnsid), packed=data)

    def json(self, compact=None):
        return '"srv6-l3vpn-sid": "%s"' % (self.l3vpnsid)
