# encoding: utf-8
"""
ifaceaddr.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import unpack

from exabgp.protocol.ip import IP
from exabgp.util import ordinal

#   https://tools.ietf.org/html/rfc5305#section-3.2
#   This sub-TLV contains a 4-octet IPv4 address for the interface
#   described by the (main) TLV.  This sub-TLV can occur multiple times.
#
#
#   https://tools.ietf.org/html/rfc6119 4.2
#    The IPv6 Interface Address sub-TLV of the Extended IS Reachability
#   TLV has sub-TLV type 12.  It contains a 16-octet IPv6 address for the
#   interface described by the containing Extended IS Reachability TLV.
#   This sub-TLV can occur multiple times.
# ================================================================== InterfaceAddress


class IfaceAddr(object):
    def __init__(self, iface_addr, packed=None):
        self.iface_address = iface_addr
        self._packed = packed

    @classmethod
    def unpack(cls, data):
        if len(data) == 4:
            # IPv4 address
            addr = IP.unpack(data[:4])
        elif len(data) == 16:
            # IPv6
            addr = IP.unpack(data[:16])
        return cls(iface_addr=addr)

    def json(self, compact=None):
        return '"interface-address": "%s"' % self.iface_address

    def __eq__(self, other):
        return self.iface_address == other.iface_address

    def __neq__(self, other):
        return self.iface_address != other.iface_address

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
