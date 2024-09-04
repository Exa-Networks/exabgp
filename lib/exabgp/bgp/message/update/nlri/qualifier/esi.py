# encoding: utf-8
"""
esi.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.util import character
from exabgp.util import ordinal
from exabgp.util import concat_bytes_i

# TODO: take into account E-VPN specs that specify the role of the first bit of ESI
# (since draft-ietf-l2vpn-evpn-05)


# Ethernet Segment Identifier
class ESI(object):
    DEFAULT = concat_bytes_i(character(0) for _ in range(0, 10))
    MAX = concat_bytes_i(character(0xFF) for _ in range(0, 10))

    __slots__ = ['esi']

    def __init__(self, esi=None):
        self.esi = self.DEFAULT if esi is None else esi
        if len(self.esi) != 10:
            raise Exception("incorrect ESI, len %d instead of 10" % len(esi))

    def __eq__(self, other):
        return self.esi == other.esi

    def __neq__(self, other):
        return self.esi != other.esi

    def __lt__(self, other):
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __le__(self, other):
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __gt__(self, other):
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __ge__(self, other):
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __str__(self):
        if self.esi == self.DEFAULT:
            return "-"
        return ":".join('%02x' % ordinal(_) for _ in self.esi)

    def __repr__(self):
        return self.__str__()

    def pack(self):
        return self.esi

    def __len__(self):
        return 10

    def __hash__(self):
        return hash(self.esi)

    @classmethod
    def unpack(cls, data):
        return cls(data[:10])

    def json(self, compact=None):
        return '"esi": "%s"' % str(self)
