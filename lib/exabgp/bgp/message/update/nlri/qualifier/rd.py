# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack

from exabgp.util import character
from exabgp.util import concat_bytes_i
from exabgp.util import hexstring


# =========================================================== RouteDistinguisher
# RFC 4364


class RouteDistinguisher(object):

    __slots__ = ['rd', '_len']

    def __init__(self, rd):
        self.rd = rd
        self._len = len(self.rd)

    def __eq__(self, other):
        return self.rd == other.rd

    def __neq__(self, other):
        return self.rd != other.rd

    def __lt__(self, other):
        raise RuntimeError('comparing RouteDistinguisher for ordering does not make sense')

    def __le__(self, other):
        raise RuntimeError('comparing RouteDistinguisher for ordering does not make sense')

    def __gt__(self, other):
        raise RuntimeError('comparing RouteDistinguisher for ordering does not make sense')

    def __ge__(self, other):
        raise RuntimeError('comparing RouteDistinguisher for ordering does not make sense')

    def pack(self):
        return self.rd

    def __len__(self):
        return self._len

    def _str(self):
        t, c1, c2, c3 = unpack('!HHHH', self.rd)
        if t == 0:
            rd = '%d:%d' % (c1, (c2 << 16) + c3)
        elif t == 1:
            rd = '%d.%d.%d.%d:%d' % (c1 >> 8, c1 & 0xFF, c2 >> 8, c2 & 0xFF, c3)
        elif t == 2:
            rd = '%d:%d' % ((c1 << 16) + c2, c3)
        else:
            rd = hexstring(self.rd)
        return rd

    def json(self):
        if not self.rd:
            return ''
        return '"rd": "%s"' % self._str()

    def __hash__(self):
        return hash(self.rd)

    def __repr__(self):
        if not self.rd:
            return ''
        return ' rd %s' % self._str()

    @classmethod
    def unpack(cls, data):
        return cls(data[:8])

    # DO NOT USE, the right function is route_distinguisher() in exabgp.configuation.static.mpls
    @classmethod
    def fromElements(cls, prefix, suffix):
        try:
            if '.' in prefix:
                data = [character(0), character(1)]
                data.extend([character(int(_)) for _ in prefix.split('.')])
                data.extend([character(suffix >> 8), character(suffix & 0xFF)])
                distinguisher = concat_bytes_i(data)
            else:
                number = int(prefix)
                if number < pow(2, 16) and suffix < pow(2, 32):
                    distinguisher = character(0) + character(0) + pack('!H', number) + pack('!L', suffix)
                elif number < pow(2, 32) and suffix < pow(2, 16):
                    distinguisher = character(0) + character(2) + pack('!L', number) + pack('!H', suffix)
                else:
                    raise ValueError('invalid route-distinguisher %s' % number)

            return cls(distinguisher)
        except ValueError:
            raise ValueError('invalid route-distinguisher %s:%s' % (prefix, suffix))


RouteDistinguisher.NORD = RouteDistinguisher(b'')
