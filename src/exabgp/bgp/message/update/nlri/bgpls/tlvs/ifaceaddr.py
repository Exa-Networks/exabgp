"""ifaceaddr.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.protocol.ip import IP, IPv4, IPv6

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


class IfaceAddr:
    def __init__(self, iface_addr, packed=None):
        self.iface_address = iface_addr
        self._packed = packed

    @classmethod
    def unpack_ifaceaddr(cls, data):
        if len(data) == IPv4.BYTES:
            # IPv4 address
            addr = IP.unpack_ip(data[: IPv4.BYTES])
        elif len(data) == IPv6.BYTES:
            # IPv6
            addr = IP.unpack_ip(data[: IPv6.BYTES])
        return cls(iface_addr=addr)

    def json(self, compact: bool = False):
        return '"{}"'.format(self.iface_address)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IfaceAddr):
            return False
        return self.iface_address == other.iface_address

    def __lt__(self, other):
        raise RuntimeError('Not implemented')

    def __le__(self, other):
        raise RuntimeError('Not implemented')

    def __gt__(self, other):
        raise RuntimeError('Not implemented')

    def __ge__(self, other):
        raise RuntimeError('Not implemented')

    def __str__(self):
        return ':'.join('{:02X}'.format(_) for _ in self._packed)

    def __repr__(self):
        return self.__str__()

    def __len__(self):
        return len(self._packed)

    def __hash__(self):
        return hash(str(self))

    def pack_tlv(self):
        return self._packed
