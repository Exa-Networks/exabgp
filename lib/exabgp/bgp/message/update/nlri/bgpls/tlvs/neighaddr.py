# encoding: utf-8
"""
neighaddr.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack

from exabgp.protocol.ip import IP
from exabgp.bgp.message.notification import Notify
from exabgp.util import ordinal

#  https://tools.ietf.org/html/rfc5305#section-3.3
#   This sub-TLV contains a single IPv4 address for a neighboring router
#   on this link.  This sub-TLV can occur multiple times.
#
#   Implementations MUST NOT inject a /32 prefix for the neighbor address
#   into their routing or forwarding table because this can lead to
#   forwarding loops when interacting with systems that do not support
#   this sub-TLV.
# ================================================================== NeighborAddress


class NeighAddr(object):
    def __init__(self, addr, packed=None):
        self.addr = addr
        self._packed = packed

    @classmethod
    def unpack(cls, data):
        if len(data) == 4:
            # IPv4 address
            addr = IP.unpack(data[:4])
        elif len(data) == 16:
            # IPv6
            addr = IP.unpack(data[:16])
        return cls(addr=addr)

    def json(self):
        content = ' '.join(['"neighbor-address": "%s"' % self.addr,])
        return content

    def __eq__(self, other):
        return self.addr == other.addr

    def __neq__(self, other):
        return self.addr != other.addr

    def __lt__(self, other):
        raise RuntimeError('Not implemented')

    def __le__(self, other):
        raise RuntimeError('Not implemented')

    def __gt__(self, other):
        raise RuntimeError('Not implemented')

    def __ge__(self, other):
        raise RuntimeError('Not implemented')

    def __str__(self):
        return ':'.join('%02X' % ordinal(_) for _ in self._packed)

    def __repr__(self):
        return self.__str__()

    def __len__(self):
        return len(self._packed)

    def __hash__(self):
        return hash(str(self))

    def pack(self):
        return self._packed
