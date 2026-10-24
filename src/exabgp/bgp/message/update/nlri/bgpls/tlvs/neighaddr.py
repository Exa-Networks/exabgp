"""neighaddr.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.notification import Notify
from exabgp.protocol.ip import IP, IPv4, IPv6

#  https://tools.ietf.org/html/rfc5305#section-3.3
#   This sub-TLV contains a single IPv4 address for a neighboring router
#   on this link.  This sub-TLV can occur multiple times.
#
#   Implementations MUST NOT inject a /32 prefix for the neighbor address
#   into their routing or forwarding table because this can lead to
#   forwarding loops when interacting with systems that do not support
#   this sub-TLV.
# ================================================================== NeighborAddress


class NeighAddr:
    def __init__(self, addr, packed=None):
        self.addr = addr
        self._packed = packed

    @classmethod
    def unpack(cls, data):
        # any other length used to leave addr unbound and an UnboundLocalError
        # escaped the decoder, so the peer was never told what was wrong.
        # the accepted widths are named once here: a guard listing them and an
        # else assuming the rest states the same rule twice, and the else would
        # silently decode as IPv6 any width later added to the guard.
        if len(data) == IPv4.BYTES:
            addr = IP.unpack(data[: IPv4.BYTES])
        elif len(data) == IPv6.BYTES:
            addr = IP.unpack(data[: IPv6.BYTES])
        else:
            raise Notify(
                3,
                10,
                'invalid BGP-LS neighbour address sub-TLV, expected %d or %d bytes, got %d'
                % (IPv4.BYTES, IPv6.BYTES, len(data)),
            )
        return cls(addr=addr)

    def json(self):
        return '"{}"'.format(self.addr)

    def as_dict(self):
        return str(self.addr)

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
        return ':'.join('{:02X}'.format(_) for _ in self._packed)

    def __repr__(self):
        return self.__str__()

    def __len__(self):
        return len(self._packed)

    def __hash__(self):
        return hash(str(self))

    def pack(self):
        return self._packed
