# encoding: utf-8
"""
sr/srv6vpnsid.py

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
# |   SID-Type    |   SID-Flags   |                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+                               |
# |                                                               |
# |                        IPv6 SID (16 octets)                   |
# |                                                               |
# |                               +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# 3.2.  SRv6 VPN SID


@PrefixSid.register()
class Srv6VpnSid(object):
    TLV = 4
    LENGTH = 19

    def __init__(self, vpnsid, packed=None):
        self.vpnsid = vpnsid
        self.packed = self.pack()

    def __repr__(self):
        return "srv6-vpn-sid %s" % (self.vpnsid)

    def pack(self):
        return concat_bytes(
            pack('!B', self.TLV),
            pack('!H', self.LENGTH),
            pack('!B', 0),
            pack('!B', 0),
            pack('!B', 0),
            IP.pton(self.vpnsid),
        )

    @classmethod
    def unpack(cls, data, length):
        vpnsid = -1
        if cls.LENGTH != length:
            raise Notify(3, 5, "Invalid TLV size. Should be {0} but {1} received".format(cls.LENGTH, length))
        data = data[3:19]
        vpnsid = IP.unpack(data)
        return cls(vpnsid=str(vpnsid), packed=data)

    def json(self, compact=None):
        return '"srv6-vpn-sid": "%s"' % (self.vpnsid)
