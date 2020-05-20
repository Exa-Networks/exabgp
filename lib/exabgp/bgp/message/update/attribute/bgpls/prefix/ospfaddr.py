# encoding: utf-8
"""
ospfaddr.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip import IP

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                Forwarding Address (variable)                //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.3.5


@LINKSTATE.register()
class OspfForwardingAddress(object):
    TLV = 1156

    def __init__(self, addr):
        self.addr = addr

    def __repr__(self):
        return "Ospf forwarding address: '%s'" % (self.addr)

    @classmethod
    def unpack(cls, data, length):
        if len(data) == 4:
            # IPv4 address
            addr = IP.unpack(data[:4])
        elif len(data) == 16:
            # IPv6
            addr = IP.unpack(data[:16])
        else:
            raise Notify(3, 5, "Error parsing OSPF Forwarding Address. Wrong size")
        return cls(addr=addr)

    def json(self, compact=None):
        return '"ospf-forwarding-address": "%s"' % str(self.addr)
