# encoding: utf-8
"""
mac.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""


from exabgp.util import character
from exabgp.util import ordinal
from exabgp.util import concat_bytes_i


# ========================================================================== MAC
#


class MAC(object):

    __slots__ = ['mac', '_packed']

    def __init__(self, mac=None, packed=None):
        self.mac = mac
        self._packed = packed if packed else concat_bytes_i(character(int(_, 16)) for _ in mac.split(":"))

    def __eq__(self, other):
        return self.mac == other.mac

    def __neq__(self, other):
        return self.mac != other.mac

    def __lt__(self, other):
        raise RuntimeError('comparing MAC for ordering does not make sense')

    def __le__(self, other):
        raise RuntimeError('comparing MAC for ordering does not make sense')

    def __gt__(self, other):
        raise RuntimeError('comparing MAC for ordering does not make sense')

    def __ge__(self, other):
        raise RuntimeError('comparing MAC for ordering does not make sense')

    def __str__(self):
        return ':'.join('%02X' % ordinal(_) for _ in self._packed)

    def __repr__(self):
        return self.__str__()

    def pack(self):
        return self._packed

    # Orange code was returning 10 !
    def __len__(self):
        return 6

    # XXX: FIXME: improve for better performance ?
    def __hash__(self):
        return hash(str(self))

    @classmethod
    def unpack(cls, data):
        return cls(':'.join('%02X' % ordinal(_) for _ in data[:6]), data[:6])

    def json(self, compact=None):
        return '"mac": "%s"' % str(self)
